

from ask_ai import db
from ask_ai.cache import TTLCache
from ask_ai.config import (
    TABLE_ALLOWLIST, HIDDEN_COLUMNS, HIDDEN_COLUMN_SUFFIXES, SCHEMA_CACHE_TTL,
)


_cache = TTLCache(SCHEMA_CACHE_TTL, max_entries=4)
_KEY = 'dbo'


def _is_hidden(column):
    return column in HIDDEN_COLUMNS or column.endswith(HIDDEN_COLUMN_SUFFIXES)


def _fetch_columns():
    """{table: [(column, type), ...]} for the allowlisted DW tables."""
    placeholders = ', '.join(['%s'] * len(TABLE_ALLOWLIST))
    rows = db.query(
        "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME IN ({placeholders}) "
        "ORDER BY TABLE_NAME, ORDINAL_POSITION",
        tuple(TABLE_ALLOWLIST),
    )

    tables = {}
    for row in rows:
        column = row['COLUMN_NAME']
        if _is_hidden(column):
            continue
        tables.setdefault(row['TABLE_NAME'], []).append((column, row['DATA_TYPE']))
    return tables


def get_columns():
    """Allowlisted DW schema, cached."""
    tables = _cache.get(_KEY)
    if tables is None:
        tables = _fetch_columns()
        _cache.set(_KEY, tables)
    return tables


def get_table_names():
    return list(get_columns().keys())


_COUNTRY_KEY = 'country_ids'


def country_ids():
    """{'KY': 1, 'TZ': 2, ...} read from DW, not hardcoded."""
    ids = _cache.get(_COUNTRY_KEY)
    if ids is None:
        rows = db.query(
            'SELECT DISTINCT CountryId, CountryCode FROM MfMember '
            'WHERE CountryCode IS NOT NULL'
        )
        ids = {r['CountryCode'].strip().upper(): int(r['CountryId']) for r in rows}
        _cache.set(_COUNTRY_KEY, ids)
    return ids


def tables_with_column(column):

    target = column.lower()
    return [table for table, cols in get_columns().items()
            if any(name.lower() == target for name, _ in cols)]


def get_schema_text(tables=None):
    """Render the schema as CREATE TABLE DDL for the prompt."""
    all_tables = get_columns()
    wanted = tables or list(all_tables.keys())

    blocks = []
    for table in wanted:
        cols = all_tables.get(table)
        if not cols:
            continue
        col_defs = ", ".join(f"{name} {dtype}" for name, dtype in cols)
        blocks.append(f"CREATE TABLE {table} ({col_defs});")
    return "\n".join(blocks)


def warm():
    """Populate the cache at startup so the first question doesn't pay for it."""
    try:
        get_columns()
        return True
    except Exception as e:
        print(f"[ask_ai] schema warm-up skipped: {e}")
        return False
