"""
ask_ai — Local natural-language Q&A over the 4-country microfinance warehouse.

Self-contained module:
  - sync_warehouse.py : pull 4 country MSSQL DBs -> local DuckDB copy
  - engine.py         : question -> SQL (local Ollama) -> run on DuckDB -> answer
  - api.py            : Flask blueprint `POST /api/ask-ai`

Nothing here touches the live MSSQL servers except the sync step, so answering a
question is fast and works offline against the local warehouse.
"""
