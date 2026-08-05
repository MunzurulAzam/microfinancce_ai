"""
Run Tool:
    python -m ask_ai.sync_warehouse                # sync all countries, all tables
    python -m ask_ai.sync_warehouse --country KY   # sync just Kenya
    python -m ask_ai.sync_warehouse --tables MfLoan MfMember

Resilience model: no query is ever "as big as the table". Every read is a small
bounded page (keyset/offset) or a one-year chunk (aggregates). Each page is
retried on a fresh connection, so a network drop or server hiccup costs one
page — never the whole table. Reads run under READ UNCOMMITTED so the sync
never waits on live OLTP locks.
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
    SYNC_PAGE_RETRIES,
    WAREHOUSE_PATH,
    DATA_DIR,
)
from ask_ai.db_sources import connect

PROGRESS_EVERY = 50_000  # print a progress line every N rows on big tables


class SkipTable(Exception):
    """Raised when a table/aggregate cannot apply to this country (e.g. the source
    table doesn't exist here) — the sync reports it as skipped, never a failure."""


def _is_permanent(e):
    """SQL errors that will not go away with a retry (missing table/column)."""
    msg = str(e)
    return (
        'Invalid object name' in msg or '(208' in msg
        or 'Invalid column name' in msg or '(207' in msg
    )


class Source:
    """MSSQL source connection that survives drops.

    Every query issued through `query()` is bounded (one page / one chunk) and
    is retried on a fresh connection after a transient failure, so long syncs
    can ride out network resets, NAT idle kills and server restarts.
    """

    def __init__(self, profile):
        self.profile = profile
        self.conn = None
        self.cur = None
        self._open()

    def _open(self):
        self.close()
        self.conn = connect(self.profile)
        self.cur = self.conn.cursor()
        # Dirty reads are fine for a reporting warehouse — never block behind
        # live OLTP writers (lock waits are a classic sync-timeout cause).
        self.cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")

    def close(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None
        self.cur = None

    def query(self, sql, params=None):
        """Run one bounded query; reconnect and retry on transient failures."""
        last_err = None
        for attempt in range(1, SYNC_PAGE_RETRIES + 1):
            try:
                if self.cur is None:
                    self._open()
                if params is None:
                    self.cur.execute(sql)
                else:
                    self.cur.execute(sql, params)
                return self.cur.fetchall()
            except Exception as e:
                if _is_permanent(e):
                    raise
                last_err = e
                self.close()
                if attempt < SYNC_PAGE_RETRIES:
                    wait = min(30, 5 * attempt)
                    print(
                        f"    … page failed (attempt {attempt}/{SYNC_PAGE_RETRIES}), "
                        f"reconnecting in {wait}s: {e}"
                    )
                    time.sleep(wait)
        raise last_err

    def stream(self, sql):
        """Last-resort single-query stream (only for tables with no usable key).
        Not page-retryable — a failure here restarts the table."""
        if self.cur is None:
            self._open()
        self.cur.execute(sql)
        while True:
            rows = self.cur.fetchmany(SYNC_BATCH_SIZE)
            if not rows:
                break
            yield rows


def _source_table_exists(src, table):
    """True if `table` exists in the connected source (MSSQL) database."""
    return bool(src.query("SELECT 1 AS ok FROM sys.tables WHERE name = %s", (table,)))


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


def _get_pagination(src, table):
    """Pick the cheapest safe paging strategy for a source table.

    Returns (mode, cols):
      ('keyset', col)   — identity / single-column PK / single-column unique
                          NOT NULL index: seek-paginate, fully resumable.
      ('offset', cols)  — composite PK/unique index: deterministic ORDER BY +
                          OFFSET/FETCH pages, resumable.
      ('stream', None)  — nothing usable: stream in one query (last resort).
    """
    #  IDENTITY column: always unique, indexed, ordered — ideal for keyset.
    rows = src.query(
        "SELECT c.name AS name FROM sys.identity_columns c "
        "JOIN sys.tables t ON c.object_id = t.object_id "
        "WHERE t.name = %s", (table,)
    )
    if rows:
        return 'keyset', rows[0]['name']

    # Primary key: single column → keyset; composite → offset over PK order.
    pk = src.query(
        "SELECT col.name AS name FROM sys.indexes i "
        "JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
        "JOIN sys.columns col ON ic.object_id = col.object_id AND ic.column_id = col.column_id "
        "JOIN sys.tables t ON i.object_id = t.object_id "
        "WHERE i.is_primary_key = 1 AND t.name = %s "
        "ORDER BY ic.key_ordinal", (table,)
    )
    if len(pk) == 1:
        return 'keyset', pk[0]['name']
    if pk:
        return 'offset', [r['name'] for r in pk]

    # Any unique index (NOT NULL keys only — NULLs break keyset seeks).
    uq = src.query(
        "SELECT i.index_id AS index_id, col.name AS name FROM sys.indexes i "
        "JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
        "JOIN sys.columns col ON ic.object_id = col.object_id AND ic.column_id = col.column_id "
        "JOIN sys.tables t ON i.object_id = t.object_id "
        "WHERE i.is_unique = 1 AND ic.is_included_column = 0 "
        "AND col.is_nullable = 0 AND t.name = %s "
        "ORDER BY i.index_id, ic.key_ordinal", (table,)
    )
    by_index = {}
    for r in uq:
        by_index.setdefault(r['index_id'], []).append(r['name'])
    for cols in by_index.values():
        if len(cols) == 1:
            return 'keyset', cols[0]
    for cols in by_index.values():
        return 'offset', cols

    return 'stream', None


def _iter_rows(src, table):

    mode, cols = _get_pagination(src, table)

    if mode == 'keyset':
        key = cols
        last = None
        while True:
            if last is None:
                rows = src.query(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) * FROM [{table}] ORDER BY [{key}]"
                )
            else:
                rows = src.query(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) * FROM [{table}] "
                    f"WHERE [{key}] > %s ORDER BY [{key}]", (last,)
                )
            if not rows:
                break
            yield rows
            last = rows[-1][key]
            if len(rows) < SYNC_BATCH_SIZE:
                break

    elif mode == 'offset':
        order = ', '.join(f'[{c}]' for c in cols)
        offset = 0
        while True:
            rows = src.query(
                f"SELECT * FROM [{table}] ORDER BY {order} "
                f"OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
                (offset, SYNC_BATCH_SIZE),
            )
            if not rows:
                break
            yield rows
            offset += len(rows)
            if len(rows) < SYNC_BATCH_SIZE:
                break

    else:
        print(f"    … {table}: no key/unique index found — streaming (not page-resumable)")
        yield from src.stream(f"SELECT * FROM [{table}]")


def _iter_derived_rows(src, spec):

    select, frm, group = spec['select'], spec['from'], spec['group_by']
    key = spec.get('key')
    chunk_col = spec.get('chunk_col')

    if key:
        # Keyset over the group key: each page aggregates only its own slice.
        last = None
        while True:
            if last is None:
                rows = src.query(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) {select} FROM {frm} "
                    f"GROUP BY {group} ORDER BY {key}"
                )
            else:
                rows = src.query(
                    f"SELECT TOP ({SYNC_BATCH_SIZE}) {select} FROM {frm} "
                    f"WHERE {key} > %s GROUP BY {group} ORDER BY {key}", (last,)
                )
            if not rows:
                break
            yield rows
            last = rows[-1][key]
            if len(rows) < SYNC_BATCH_SIZE:
                break

    elif chunk_col:
        # Aggregate one calendar year at a time — bounded, retryable chunks.
        # Safe because the GROUP BY includes the date parts of chunk_col, so
        # no group ever spans two chunks.
        chunk_from = spec.get('chunk_from', frm)
        bounds = src.query(
            f"SELECT YEAR(MIN({chunk_col})) AS y0, YEAR(MAX({chunk_col})) AS y1 "
            f"FROM {chunk_from}"
        )[0]
        if bounds['y0'] is not None:
            for year in range(bounds['y0'], bounds['y1'] + 1):
                rows = src.query(
                    f"SELECT {select} FROM {frm} "
                    f"WHERE {chunk_col} >= %s AND {chunk_col} < %s "
                    f"GROUP BY {group}",
                    (f"{year}-01-01", f"{year + 1}-01-01"),
                )
                if rows:
                    yield rows
        rows = src.query(
            f"SELECT {select} FROM {frm} WHERE {chunk_col} IS NULL GROUP BY {group}"
        )
        if rows:
            yield rows

    else:
        rows = src.query(f"SELECT {select} FROM {frm} GROUP BY {group}")
        if rows:
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
            prev = loaded
            loaded += len(df)
            if loaded // PROGRESS_EVERY != prev // PROGRESS_EVERY:
                print(f"    … {table_name}: {loaded:,} rows so far")

        con.execute("COMMIT")
        return loaded
    except Exception:
        con.execute("ROLLBACK")
        raise


def _sync_raw_table(con, profile, table):
    """Copy a raw source table keyset-paginated into the warehouse."""
    src = Source(profile)
    try:
        if not _source_table_exists(src, table):
            raise SkipTable(f"not in {profile['country']}")
        return _load_into_duckdb(con, profile['country'], table, _iter_rows(src, table))
    finally:
        src.close()


def _sync_derived_table(con, profile, spec):
    """Pull a server-side aggregate into the warehouse in bounded chunks."""
    src = Source(profile)
    try:
        missing = [t for t in spec.get('requires', []) if not _source_table_exists(src, t)]
        if missing:
            raise SkipTable(f"needs {', '.join(missing)} (not in {profile['country']})")
        return _load_into_duckdb(con, profile['country'], spec['name'], _iter_derived_rows(src, spec))
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
            if _is_permanent(e):
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
