# ask_ai — 4-Country Natural-Language Q&A (Text-to-SQL)

Ask questions in plain language about the 4 country databases
(**UG / KY / ZM / TZ**) and get **fast, accurate answers locally**, powered by a
local Ollama model.


## Why this design (not "training a model on the data")

- A model trained on loan tables would be **stale instantly** (data changes daily)
  and would **hallucinate numbers** — unacceptable for finance.
- Instead: the model only writes **SQL**; the exact numbers always come from the
  data. Accurate, current, and runs on a **CPU laptop**.
- "Improving the model" = adding more verified `question → SQL` examples in
  [`glossary.py`](glossary.py) — **no GPU, no retraining**.

```
question ─▶ engine.py ─▶ local Ollama (SQL) ─▶ guardrail ─▶ DuckDB warehouse ─▶ answer
                                                              ▲
                                          sync_warehouse.py ──┘ (the only step that
                                                                  touches live MSSQL)
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | 4 country connection profiles + warehouse path + model name (all env-overridable) |
| `db_sources.py` | MSSQL connection factory |
| `sync_warehouse.py` | ETL: copy the 4 DBs → `data/warehouse.duckdb` (tagged by `country`) |
| `schema.py` | Reads the warehouse schema to feed the model |
| `glossary.py` | Business definitions + verified example queries (the model's knowledge) |
| `engine.py` | question → SQL → guardrail → run → answer |
| `api.py` | Flask blueprint: `POST /api/ask-ai` |

> Dependency: this module needs `duckdb`, which is listed in the **project's
> top-level `requirements.txt`** (no separate requirements file here).

### What's in the warehouse

Raw copies of the analytic tables (`MfMember`, `MfLoan`, `MfGroup`, `AdBranch`,
`HrEmployee`, `MfMemberBusiness`, `MfMemberAdditionalInfo`, `MfLoanGrantor`),
each tagged with a `country` column.

`MfLoanCollection` is **NOT copied raw** — it is ~13M rows/country and too slow to
pull over the remote link. Instead the sync pulls two small **server-side
aggregates** (fast, computed on SQL Server) that cover the reports you need:

| Warehouse table | Grain | Use for |
|-----------------|-------|---------|
| `LoanCollectionSummary` | one row per loan | overdue (count + amount), total collected per loan |
| `CollectionMonthly` | branch × officer × month | collection **trend** over time |

Outstanding figures come straight from `MfLoan` (`PrincipalOutstanding`,
`InterestOutstanding`, `TotalOutstanding`) — no collection detail required.
Add or change these in `DERIVED_TABLES` in [config.py](config.py).

## Setup

```bash
# 1. Install dependencies (duckdb is included in the project's requirements.txt)
pip install -r requirements.txt

# 2. Make sure a local code model is available (default: deepseek-coder:6.7b,
#    already used by this project). For a specialized alternative:
#      ollama pull sqlcoder:7b   &&   export ASK_AI_MODEL=sqlcoder:7b
ollama pull deepseek-coder:6.7b

# 3. Build the local warehouse from the 4 country databases (first run)
python -m ask_ai.sync_warehouse
```

The warehouse is a single file: `ask_ai/data/warehouse.duckdb` (gitignored).

## Ask questions

The endpoint is registered in the main app:

```bash
curl -X POST http://localhost:5001/api/ask-ai \
  -H 'Content-Type: application/json' \
  -d '{"question": "Total loan portfolio across all countries?"}'
```

Response:

```json
{
  "success": true,
  "answer": "The combined active loan portfolio across all 4 countries is ...",
  "sql": "SELECT SUM(PrincipalAmount) ... ",
  "columns": ["total_portfolio"],
  "rows": [{"total_portfolio": 12345678}],
  "row_count": 1
}
```

Add `"summary": false` for the fastest response (skips the natural-language
phrasing and returns the table only).

You can also call the engine directly from Python:

```python
from ask_ai.engine import ask
print(ask("How many active members in Tanzania?"))
```

## Keeping data fresh / adding a country later

Re-run the sync (e.g. nightly via cron / Windows Task Scheduler):

```bash
python -m ask_ai.sync_warehouse                 # refresh everything
python -m ask_ai.sync_warehouse --country KY    # refresh just Kenya
```

**To add a NEW connection string / country later:** add a profile to `COUNTRIES`
in [`config.py`](config.py) and run `python -m ask_ai.sync_warehouse --country XX`.
That's it — **no model retraining**. Because each row is tagged by `country`,
a re-sync of one country **never touches** the others, and data already synced
stays answerable even if a source connection string later changes or is removed
(answers come from the local warehouse, not the live DB).

## Safety

- Generated SQL is guarded: **SELECT-only**, write/DDL keywords are rejected, and
  a `LIMIT` is auto-applied. Queries run on a **read-only** DuckDB connection, and
  the warehouse is only a copy — your production MSSQL is never written to.
- Credentials are env-overridable; in production set `MSSQL_*` via environment
  variables and keep `ask_ai/data/` out of git (already in `.gitignore`).
