

import duckdb

from ask_ai.config import WAREHOUSE_PATH


def _fetch_columns():
    """Return {table_name: [(column, type), ...]} from the warehouse."""
    con = duckdb.connect(WAREHOUSE_PATH, read_only=True)
    try:
        rows = con.execute(
            "SELECT table_name, column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'main' "
            "ORDER BY table_name, ordinal_position"
        ).fetchall()
    finally:
        con.close()

    tables = {}
    for table_name, column, dtype in rows:
        tables.setdefault(table_name, []).append((column, dtype))
    return tables


def get_table_names():
    """List of tables currently in the warehouse."""
    return list(_fetch_columns().keys())


def get_schema_text(tables=None):

    all_tables = _fetch_columns()
    wanted = tables or list(all_tables.keys())

    blocks = []
    for table in wanted:
        cols = all_tables.get(table)
        if not cols:
            continue
        col_defs = ", ".join(f"{name} {dtype}" for name, dtype in cols)
        blocks.append(f"CREATE TABLE {table} ({col_defs});")
    return "\n".join(blocks)
