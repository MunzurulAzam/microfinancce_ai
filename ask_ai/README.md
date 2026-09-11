# ask_ai — natural-language Q&A over the DW warehouse

Ask a question in plain English, get a real answer computed from real data.

```
question ─▶ prompt (schema + glossary + few-shot)
         ─▶ Ollama Cloud writes T-SQL
         ─▶ guardrail (SELECT-only, single statement, TOP cap, country filter)
         ─▶ dry-run validation on DW  ──(error)──▶ one repair retry
         ─▶ execute on DW inside a rolled-back transaction
         ─▶ answer + table
```

**For warehouse Q&A, the model writes SQL and summarizes results.** Every number in an answer comes straight from
DW, because an LLM that invents figures is useless — and dangerous — in finance.

## Why not fine-tune a model on the data?

That was the original idea, and it does not work here. Transactional data changes
daily, so a trained model is stale the day after training, and language models
hallucinate numbers. Text-to-SQL keeps the model doing what it is good at
(turning English into a query) and the database doing what it is good at
(arithmetic).

## Why no local cache / copy of the warehouse?

There used to be one — a 340 MB DuckDB file rebuilt nightly from four separate
per-country MSSQL databases. It existed to stitch those four databases into one
queryable thing.

`DW` already is that. Every table carries `CountryId` and `CountryCode`
(UG / KY / ZM / TZ), so one connection answers both single-country and
cross-country questions. And DW is fast: portfolio-by-country returns in ~0.3 s,
a monthly trend over the 20.6M-row `MfLoanCollection` in ~1 s. A local copy would
add staleness and a nightly ETL to maintain, and buy nothing.

## Files

| File | What it does |
|---|---|
| `config.py` | DW credentials (from env), table allowlist, pool + cache knobs |
| `db.py` | Connection pool, `validate_sql()`, `run_sql()`, `query()` |
| `cache.py` | Small TTL cache (schema + results) |
| `schema.py` | Cached `INFORMATION_SCHEMA` introspection of the allowlisted tables |
| `glossary.py` | Business rules, metric CTEs, verified question→SQL examples |
| `prompt.py` | Table routing + prompt assembly |
| `sql_guard.py` | Makes model output safe: one read-only SELECT, capped, country-scoped |
| `llm.py` | Ollama client (`/api/generate`), retries, actionable errors |
| `engine.py` | Orchestration: route → generate → validate → repair → execute |
| `member_analysis.py` | The other branch: credit score + decision for one member |
| `api.py` | Flask blueprint `POST /api/ask-ai` |
| `dify.py` | Flask blueprint `POST /api/dify/retrieval` — Dify external knowledge API |
| `dify_records.py` | Turns an engine answer / the schema into Dify `records` |
| `check_examples.py` | Self-check: runs every example against DW + asserts routing |

## Setup

```bash
cp .env.example .env      # then fill in DW_* credentials
# set OLLAMA_API_KEY in .env (no local Ollama install needed)
python app.py
```

## Use

```bash
curl -X POST http://localhost:5001/api/ask-ai \
  -H 'Content-Type: application/json' \
  -d '{"question": "Total outstanding portfolio by country?"}'
```

| Field | Meaning |
|---|---|
| `question` | required |
| `country` | `UG` / `KY` / `ZM` / `TZ`, or omit / `ALL` for all four |
| `summary` | `false` skips the natural-language sentence — fastest path |

`country` is a real filter, not a hint: the guard rejects any generated SQL that
does not carry `CountryCode = '<country>'`, and rejects SQL that filters on a
different country.

Response: `{success, question, sql, columns, rows, row_count, answer, mode}`.
The `sql` is always returned so a wrong answer is easy to diagnose.

## Dify external knowledge base

Dify can use this warehouse as an **external knowledge base**: for every user
message it POSTs `{endpoint}/retrieval`, and whatever `records` come back are
injected into its LLM's context. One endpoint serves two knowledge bases:

| `knowledge_id` | Records returned |
|---|---|
| `dw-live` | The question run through `engine.route()` — answer sentence, result rows as a markdown table, and the SQL. Live numbers. |
| `dw-schema` | Business rules (`GLOSSARY`), verified example SQL, and `CREATE TABLE` DDL for the tables the question routes to. |

`dw-schema` ranks records with the same keyword routing the prompt uses, not
embedding similarity — scores are stable, not cosine distances.

Set `DIFY_KB_API_KEY` in `.env` (empty key = endpoint closed, never open) and
test it locally:

```bash
curl -X POST http://localhost:5001/api/dify/retrieval \
  -H 'Authorization: Bearer <DIFY_KB_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"knowledge_id": "dw-live", "query": "Total outstanding portfolio by country?",
       "retrieval_setting": {"top_k": 5, "score_threshold": 0.2}}'
```

A country filter arrives as Dify's `metadata_condition` — a condition named
`country` with value `UG` / `KY` / `ZM` / `TZ` — and is passed to the engine as
the same hard `country` filter `/api/ask-ai` uses.

Wiring it up in Dify: **Knowledge → External Knowledge API → Add**, with
`API Endpoint` = `https://<public-host>/api/dify` (Dify appends `/retrieval`
itself) and the API key. Then **Create Knowledge → Connect to an External
Knowledge Base**, with Knowledge ID `dw-live` or `dw-schema`.

Dify Cloud cannot reach `localhost`, so expose the server first — e.g.
`ngrok http 5001` — and update the endpoint whenever the tunnel URL changes.
Behind a public tunnel, run Flask with `debug=False`.

A question the engine cannot answer returns `200 {"records": []}`, not an error:
Dify treats any non-200 as a hard failure, and no context is better than a dead
workflow. The reason is logged server-side. Auth and knowledge-id problems do
use Dify's own codes — `1001` bad header, `1002` wrong key, `2001` unknown
knowledge id.

## Improving accuracy

Accuracy comes from the prompt, not the database. In order of impact:

1. Add a verified question→SQL pair to `EXAMPLES` in `glossary.py`.
2. Correct or extend the rules in `GLOSSARY`.
3. Add keywords to `_TABLE_KEYWORDS` in `prompt.py` so the right table reaches
   the prompt.

After any change to `EXAMPLES` or to the router, run:

```bash
python -m ask_ai.check_examples
```

It checks two things, neither needing the LLM: every example still executes
against DW, and questions route to the right pipeline. An example that does not
run is a prompt actively teaching the model to be wrong.

### Rules that matter most

- **`LoanStatus = 1` is the only active status.** `TotalOutstanding` is *not*
  zeroed when a loan closes, so an unfiltered portfolio total comes out roughly
  5× too large.
- **Every join must also match `CountryId`.** Business ids are only unique within
  a country; without it, rows multiply across countries.
- **`MfMember` has no `BranchId`.** A member reaches a branch only through
  `MfMember.GroupId → MfGroup.BranchId → AdBranch`. DW declares no foreign keys,
  so every join path lives in `JOIN_RULES` in `glossary.py` — that block is
  shared by the first prompt and the repair prompt.
- **member = client = customer = user.** All mean `MfMember`. Only *borrower*
  differs: it implies an active loan.

### Routing

Credit analysis is for one identifiable person. A `CLN…` code (or a bare member
id) routes there outright; a phrase like "assess client X" routes there only if
the question has no aggregate wording (`total`, `list`, `all`, `how many`,
`branch`, `each`, …). That veto is what stops "give me Nyangusu this branch
total member name" being read as somebody's name.

## Safety

The DW login has write and DDL rights, so model output passes four independent
layers before anything touches the server:

1. **Guard** (`sql_guard.py`) — one statement only, must start `SELECT`/`WITH`,
   write/DDL keywords rejected (checked outside string literals, so
   `WHERE MemberStatus = 'Deleted'` is fine), `TOP (n)` injected, country filter
   enforced.
2. **Dry run** (`db.validate_sql`) — `sp_describe_first_result_set` compiles the
   query without executing it (~0.4 s), catching hallucinated tables and columns.
3. **Rolled-back transaction** — execution is wrapped in `BEGIN TRANSACTION` …
   `ROLLBACK`, so a write that somehow got through still cannot commit.
4. **Limits** — `READ UNCOMMITTED` and `LOCK_TIMEOUT` so an analytical scan never
   blocks a production writer; a statement timeout; and a row cap.

`AcVoucherMaster` / `AcVoucherDetail` (44M / 109M rows, clustered PK only) are
deliberately left out of the allowlist — any ad-hoc aggregate over them is a
guaranteed full scan.

## Named management reports

Ask `Group Performance Report August 2026` for a structured preview and PDF.
The report route uses fixed historical queries and a saved snapshot.
See [the report API contract](../docs/report-api.md) for model setup, data definitions, FX configuration and .NET examples.
