"""
Run Tool:
    python -m ask_ai.sync_warehouse                # sync all countries, all tables
    python -m ask_ai.sync_warehouse --country KY   # sync just Kenya
    python -m ask_ai.sync_warehouse --tables MfLoan MfMember
"""

import argparse
import os
import time
from decimal import Decimal

import duckdb
import pandas as pd

from ask_ai.config import (
    COUNTRIES,
    COUNTRIES_BY_CODE,
    SYNC_TABLES,
    DERIVED_TABLES,
    SYNC_BATCH_SIZE,
    SYNC_RETRIES,
    WAREHOUSE_PATH,
    DATA_DIR,
)
from ask_ai.db_sources import connect


class SkipTable(Exception):
    """Raised when a table/aggregate cannot apply to this country (e.g. the source
    table doesn't exist here) — the sync reports it as skipped, never a failure."""


def _source_table_exists(cur, table):
    """True if `table` exists in the connected source (MSSQL) database."""
    cur.execute("SELECT 1 AS ok FROM sys.tables WHERE name = %s", (table,))
    return cur.fetchone() is not None


def _coerce_decimals(df):

    for col in df.columns:
        if df[col].dtype != object:
            continue
        first = next((v for v in df[col] if v is not None), None)
        if isinstance(first, Decimal):
            df[col] = df[col].astype(float)
    return df


def _table_exists(con, table):
    row = con.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = ?",
        [table],
    ).fetchone()
    return row is not None


def _get_key_column(cur, table):

    #  IDENTITY column always unique, indexed, ordered  ideal for keyset.
    cur.execute(
        "SELECT c.name AS name FROM sys.identity_columns c "
        "JOIN sys.tables t ON c.object_id = t.object_id "
        "WHERE t.name = %s", (table,)
    )
    row = cur.fetchone()
    if row:
        return row['name']

    # Single-column primary key.
    cur.execute(
        "SELECT col.name AS name FROM sys.indexes i "
        "JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
        "JOIN sys.columns col ON ic.object_id = col.object_id AND ic.column_id = col.column_id "
        "JOIN sys.tables t ON i.object_id = t.object_id "
        "WHERE i.is_primary_key = 1 AND t.name = %s", (table,)
    )
    pk = cur.fetchall()
    return pk[0]['name'] if len(pk) == 1 else None


def _iter_rows(cur, table, key):

    if key:
        last = None
        while True:
            if last is None:
                cur.execute(f"SELECT TOP ({SYNC_BATCH_SIZE}) * FROM [{table}] ORDER BY [{key}]")
            else:
                cur.execute(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) * FROM [{table}] "
                    f"WHERE [{key}] > %s ORDER BY [{key}]", (last,)
                )
            rows = cur.fetchall()
            if not rows:
                break
            yield rows
            last = rows[-1][key]
            if len(rows) < SYNC_BATCH_SIZE:
                break
    else:
        cur.execute(f"SELECT * FROM [{table}]")
        while True:
            rows = cur.fetchmany(SYNC_BATCH_SIZE)
            if not rows:
                break
            yield rows


def _iter_derived_rows(cur, spec):

    select, frm, group = spec['select'], spec['from'], spec['group_by']
    key = spec.get('key')

    if key:
        last = None
        while True:
            if last is None:
                cur.execute(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) {select} FROM {frm} "
                    f"GROUP BY {group} ORDER BY {key}"
                )
            else:
                cur.execute(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) {select} FROM {frm} "
                    f"WHERE {key} > %s GROUP BY {group} ORDER BY {key}", (last,)
                )
            rows = cur.fetchall()
            if not rows:
                break
            yield rows
            last = rows[-1][key]
            if len(rows) < SYNC_BATCH_SIZE:
                break
    else:
        cur.execute(f"SELECT {select} FROM {frm} GROUP BY {group}")
        while True:
            rows = cur.fetchmany(SYNC_BATCH_SIZE)
            if not rows:
                break
            yield rows


def _reconcile_columns(con, table_name):

    incoming = con.execute("DESCRIBE SELECT * FROM _incoming").fetchall()   # (name, type, ...)
    existing = {row[1] for row in con.execute(f'PRAGMA table_info("{table_name}")').fetchall()}
    for name, col_type, *_ in incoming:
        if name not in existing:
            con.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {col_type}')


def _load_into_duckdb(con, country, table_name, row_iter):

    con.execute("BEGIN TRANSACTION")
    try:

        if _table_exists(con, table_name):
            con.execute(f'DELETE FROM "{table_name}" WHERE country = ?', [country])

        loaded = 0
        created = _table_exists(con, table_name)
        for rows in row_iter:
            df = pd.DataFrame(rows)
            df.insert(0, 'country', country)          # country as the first column
            _coerce_decimals(df)                       # Decimal float avoid narrow DECIMAL overflow
            con.register('_incoming', df)

            if not created:
                # Create the table schema from the first incoming batch.
                con.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM _incoming')
                created = True
            else:

                _reconcile_columns(con, table_name)
                con.execute(f'INSERT INTO "{table_name}" BY NAME SELECT * FROM _incoming')

            con.unregister('_incoming')
            loaded += len(df)

        con.execute("COMMIT")
        return loaded
    except Exception:
        con.execute("ROLLBACK")
        raise


def _sync_raw_table(con, profile, table):
    """Copy a raw source table keyset-paginated into the warehouse."""
    src = connect(profile)
    cur = src.cursor()
    try:
        if not _source_table_exists(cur, table):
            raise SkipTable(f"not in {profile['country']}")
        key = _get_key_column(cur, table)
        return _load_into_duckdb(con, profile['country'], table, _iter_rows(cur, table, key))
    finally:
        src.close()


def _sync_derived_table(con, profile, spec):
    """Pull a server-side aggregate into the warehouse small, fast."""
    src = connect(profile)
    cur = src.cursor()
    try:
        missing = [t for t in spec.get('requires', []) if not _source_table_exists(cur, t)]
        if missing:
            raise SkipTable(f"needs {', '.join(missing)} (not in {profile['country']})")
        return _load_into_duckdb(con, profile['country'], spec['name'], _iter_derived_rows(cur, spec))
    finally:
        src.close()


def _ensure_country_index(con, table):
    """A simple index on `country` speeds up per-country filters."""
    try:
        idx = f"idx_{table}_country"
        con.execute(f'CREATE INDEX IF NOT EXISTS "{idx}" ON "{table}" (country)')
    except Exception:
        pass  # indexes are an optimisation, never fatal


def _run_with_retry(con, label, table_name, fn):
    """Run a table load with retry + timing; return rows loaded (0 on failure)."""
    t0 = time.time()
    for attempt in range(1, SYNC_RETRIES + 1):
        try:
            n = fn()
            _ensure_country_index(con, table_name)
            print(f"  {label:<26} {n:>10,} rows  ({time.time() - t0:.1f}s)")
            return n
        except SkipTable as e:
            print(f"  {label:<26} skipped ({e})")
            return 0
        except Exception as e:
            # "Invalid object name" SQL error 208 is permanent — don't retry.
            permanent = 'Invalid object name' in str(e) or '(208' in str(e)
            if permanent:
                print(f"  {label:<26} skipped (not available: {e})")
                return 0
            if attempt < SYNC_RETRIES:
                wait = 3 * attempt
                print(f"  {label:<26} attempt {attempt} failed, retrying in {wait}s… ({e})")
                time.sleep(wait)
            else:
                print(f"  {label:<26} FAILED after {SYNC_RETRIES} attempts: {e}")
    return 0


def sync(countries=None, tables=None):

    os.makedirs(DATA_DIR, exist_ok=True)

    profiles = (
        [COUNTRIES_BY_CODE[c.upper()] for c in countries] if countries else COUNTRIES
    )

    if tables:
        wanted = set(tables)
        raw_tables = [t for t in SYNC_TABLES if t in wanted]
        derived = [d for d in DERIVED_TABLES if d['name'] in wanted]
    else:
        raw_tables = SYNC_TABLES
        derived = DERIVED_TABLES

    con = duckdb.connect(WAREHOUSE_PATH)
    grand_total = 0
    try:
        for profile in profiles:
            print(f"\n=== {profile['country']}  ({profile['database']}) ===")
            for table in raw_tables:
                grand_total += _run_with_retry(
                    con, table, table, lambda t=table: _sync_raw_table(con, profile, t)
                )
            for spec in derived:
                grand_total += _run_with_retry(
                    con, spec['name'], spec['name'], lambda s=spec: _sync_derived_table(con, profile, s)
                )
    finally:
        con.close()

    print(f"\nDone. {grand_total:,} rows in {WAREHOUSE_PATH}")
    return grand_total


def main():
    parser = argparse.ArgumentParser(description="Sync country DBs into the local warehouse.")
    parser.add_argument(
        '--country', nargs='+', metavar='CODE',
        help='One or more country codes (UG KY ZM TZ). Default: all.',
    )
    parser.add_argument(
        '--tables', nargs='+', metavar='TABLE',
        help='Specific tables to sync. Default: all configured tables.',
    )
    args = parser.parse_args()
    sync(countries=args.country, tables=args.tables)


if __name__ == '__main__':
    main()
