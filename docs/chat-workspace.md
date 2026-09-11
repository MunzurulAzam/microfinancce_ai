# Browser chat workspace and API context

The `/` workspace restores the last active conversation. `/chat/:id` opens a saved conversation, `/?new=1` opens the unsent draft, and the legacy `/ask-ai` route opens a new Data Q&A draft. Ask AI and Data Q&A remain separate conversation modes; use New Chat to change mode. Evaluation, uploads and document tools remain separate routes.

## Storage and request lifecycle

`frontend/src/chat/store.js` owns IndexedDB `umoja-chat-workspace`, version 1. `conversations` stores title, immutable mode, selected country, draft, timestamps, sequence and pending request; `messages` stores user/assistant messages including the full structured server response. `settings` stores lastActive and the unsent newDraft. Titles use the first 60 Unicode characters of the first question. A blank chat is only created after sending.

Begin writes the user message and pending assistant placeholder in one transaction, before HTTP. Finish updates only the matching request ID. Retry reuses the assistant placeholder and original country/question; it does not duplicate the user message. Deleted conversations retain a minimal ID tombstone and lose their message records. Late replies cannot revive them. Metadata edits cannot overwrite pending state or change an existing conversation's mode.

`runtime.js` continues requests when React navigates to another app page. Web Locks serialize each conversation across tabs. Reload reclaims unlocked pending requests as Interrupted; it never automatically resends. Browsers without Web Locks use the atomic IndexedDB pending guard and a conservative four-minute recovery delay, longer than the three-minute HTTP timeout. BroadcastChannel synchronizes tabs; focus and 30-second checks provide fallback refresh/recovery. Simultaneous draft edits use last committed write wins. A failed transaction does not evict existing history; a visible error explains that history could not be saved/loaded. A failed response save leaves a pending item for explicit recovery/retry.

History belongs to the browser origin/profile. There is no login isolation, cross-device sync or backend chat-history database. Clearing browser data or browser eviction can remove it. Old unsaved chats cannot be recovered. Deployments must keep the same frontend origin to retain access to existing history and configure SPA fallback for `/chat/*`.

Report previews use the saved structured response. PDF downloads use the original server snapshot ID. A missing snapshot gives a visible error and a button preparing a new report question; the user sends it as a new message. Existing previews are never silently replaced.

## Backward-compatible API additions

Both `POST /api/ask` and `POST /api/ask-ai` accept an optional `context` array. Old requests with only `question` still work. Ask AI with an explicit non-ALL country uses the warehouse pipeline to enforce that filter; legacy CSV-only answers are not presented as country-filtered results.

```json
{
  "question": "এবার July 2026-এরটা দেখাও",
  "country": "UG",
  "context": [
    {
      "role": "assistant",
      "text": "Group performance report for 2026-08",
      "metadata": {
        "report_type": "group-performance",
        "period": "2026-08",
        "country": "UG"
      }
    }
  ]
}
```

Context is at most six messages, each with `role` (`user` or `assistant`), `text` (max 1500 characters) and optional `metadata`. Only `report_type`, `period`, `country`, `entity` (max 160 characters each) and `resolved_question` (max 1500) are accepted. Period uses YYYY-MM, country is ALL/UG/KY/TZ/ZM and report_type is group-performance. Total serialized UTF-8 context is limited to 14000 bytes. Invalid context returns HTTP 400 with `code: invalid_context`. The client stays below 13500 bytes by dropping oldest context entries, and excludes pending/failed messages, images, table rows and credit-card numeric details.

Responses retain their existing fields and add `resolved_question` and `context_metadata`. Clarifications return HTTP 200, `success: true`, `mode: clarification`, `needs_clarification: true`, and `answer`. Display them as messages, not as financial results.

Explicit report month follow-ups resolve without cloud inference and use the prior report year when only a month is given. Explicit `country` always wins, including ALL. Other referential questions use the shared cloud client to resolve a standalone question, then run the existing guarded pipeline. Cloud failure or malformed/ambiguous output requests a full question. Context is untrusted reference text, never executable SQL or a fresh financial-data source. No previous table is used for new financial calculations.

### .NET forwarding example

The browser owns history; .NET forwards the bounded context with the question. Reuse the existing configured HttpClient and server-only authentication setup; do not send database credentials or cloud keys from the browser.

```csharp
using System.Net.Http.Json;
using System.Text.Json;

var payload = new {
    question = "Now July 2026",
    country = "UG",
    context = new[] {
        new {
            role = "assistant",
            text = "Group performance report for 2026-08",
            metadata = new {
                report_type = "group-performance",
                period = "2026-08", country = "UG"
            }
        }
    }
};
// PythonClient is an injected/reused HttpClient with the Python API BaseAddress.
using var response = await pythonClient.PostAsJsonAsync("api/ask-ai", payload, cancellationToken);
var json = await response.Content.ReadAsStringAsync(cancellationToken);
// Forward the original HTTP status and JSON, including clarification/error fields.
// Set HttpClient timeout >= 180 seconds, with caller cancellation as appropriate.
```

## Verification

Run `npm test --prefix frontend`, `npm run lint --prefix frontend`, `npm run build --prefix frontend` and `.venv/bin/python -m unittest tests.test_conversation tests.test_cloud_reports` from the repository root.

For deterministic browser QA without DW/cloud calls, run `.venv/bin/python tests/chat_fixture_server.py` and start Vite with `VITE_API_BASE_URL=http://127.0.0.1:5091/api npm run dev --prefix frontend -- --host 127.0.0.1 --port 5191`. This fixture explicitly labels synthetic answers; it is a development test tool, never a production API. Questions containing `slow` delay 15 seconds for reload/tab tests; report questions produce a synthetic preview with a deliberately missing PDF snapshot.

Automated checks cover context bounds, English/Bangla report months, scope precedence, malformed context/cloud output, cloud failure, structured snapshot persistence, atomic concurrent sends, retry IDs, delete tombstones, drafts and transaction rollback. Browser QA covers desktop/mobile layout, history search/rename, new chat, refresh with draft/table/report restoration, interrupted request/retry, and live cross-tab updates. Cloud rewrite accuracy with real business phrasing still depends on a configured Ollama Cloud account and should be evaluated with representative questions before rollout.

## Warehouse Cloud configuration and report month discovery

The Python application loads `.env` relative to `app.py` (not the terminal working directory); deployment environment variables take precedence. Set `OLLAMA_API_KEY` on that Python host and restart its workers. Never enter the key in frontend configuration or chat. `GET /health` now includes `cloud.configured`, a safe configuration code and `authentication_verified: false` (health checks do not incur model calls). Run `.venv/bin/python -m core.check_cloud` on the Python host for a small live SQL-model authentication check; exit code 0 confirms successful inference. The command prints no credentials. Startup warns if cloud configuration is missing, while fixed-query reports remain available.

SQL errors preserve `code`, `http_status` and `retryable`. Missing/invalid credentials, invalid cloud configuration and unavailable model require administrator action and do not show a Retry button. Timeout/rate-limit/database errors remain distinguishable from missing report data. Failed structured responses are saved in IndexedDB so period choices and error behavior survive refresh.

`GET /api/reports/group-performance/periods?country=ALL` returns:

```json
{
  "success": true,
  "country": "ALL",
  "periods": [{
    "period": "2026-07",
    "available_countries": ["KY", "UG", "ZM"],
    "missing_countries": ["TZ"],
    "coverage": "partial",
    "snapshot_rows": 184
  }],
  "basis": "Available month-end outstanding snapshots; country coverage is not a guarantee of metric reconciliation."
}
```

The response lists completed month-end outstanding snapshots in descending order, scoped by country. A database outage returns HTTP 503 (`warehouse_unavailable`), never a misleading empty periods list. Country coverage does not certify PAR, FX or source-data completeness. Explicit report periods accept YYYY-MM or YYYY-M and Bengali digits; report output always uses YYYY-MM. Named English/Bangla months support historical four-digit years. Current/future incomplete months are rejected. Historical reports require actual snapshots; they do not use current balances or switch to August.

Missing/required/incomplete-period errors on both report entrypoints include `available_periods`, `country` and `retryable: false` where catalog lookup succeeds. If availability lookup fails, `availability_error: warehouse_unavailable` is supplied instead. Month buttons prepare a new question; pressing Send creates the new report while retaining previous history. Missing previous month or individual countries gives unavailable metrics rather than substituting another period.

.NET can forward the catalog without transformation:

```csharp
using var response = await pythonClient.GetAsync(
    "api/reports/group-performance/periods?country=UG", cancellationToken);
var json = await response.Content.ReadAsStringAsync(cancellationToken);
// Preserve the response status and JSON, including 503 and partial coverage.
```

Additional regression tests: `.venv/bin/python -m unittest tests.test_warehouse_periods tests.test_conversation tests.test_cloud_reports`.

### Signed-in Ollama transport (current default)

`OLLAMA_TRANSPORT=local_cloud` now sends the same cloud inference requests through `OLLAMA_BASE_URL=http://127.0.0.1:11434`. The local Ollama app/daemon must be running and signed in on the Python host. Python does not require or forward `OLLAMA_API_KEY` in this mode. Cloud model tags are retained (`qwen3.5:397b-cloud`, `minimax-m3:cloud`); computation remains on Ollama Cloud, without fallback to local models. All report, query, credit scoring and context pipelines are unchanged.

Set `OLLAMA_TRANSPORT=direct_cloud` explicitly only if using the direct API setup described above. `/health` includes the selected transport; configuration readiness does not imply a running daemon, signed-in session or account entitlement. Run `python -m core.check_cloud` on the same host for a live request check. HTTP 401/403 requests local sign-in; HTTP 402 returns `cloud_access_required` and requires the account's subscription/usage credits, not a Python API key. Restart Python workers after environment changes.

### Current starter-access model selection

`core/cloud.py` tries free models in order under one request deadline (`chain_for(task)`):

| task | 1st | 2nd | 3rd |
|---|---|---|---|
| sql | `ASK_AI_MODEL` (`gpt-oss:120b-cloud`, think `medium`) | `OLLAMA_FALLBACK_MODEL` (`nemotron-3-super:cloud`) | Groq `GROQ_MODEL` (`openai/gpt-oss-120b`), only when `GROQ_API_KEY` is set |
| text / report | `OLLAMA_MODEL` / `REPORT_AI_MODEL` (`gpt-oss:120b-cloud`, think `low`) | same | same |
| vision | `OLLAMA_VISION_MODEL` (`gemma4:31b-cloud`) | — | — (images never leave Ollama) |

GPT-OSS ignores `think: false`, so the client sends an explicit effort and adds 1024 tokens of reasoning headroom; otherwise small budgets returned empty `done_reason=length` replies. Any failure (busy, quota, 402, Ollama not running) moves to the next model while at least 3 s of the deadline remain; if all fail, the first model's error is returned. Successful results include `provider` and `model`. On 2026-09-11 the free account could use gpt-oss 120b/20b, gemma4:31b and nemotron-3 super/ultra/nano; glm-5.x, kimi, qwen3.5, deepseek-v4, minimax and mistral-large returned 402. Gemini's free tier was not used because Google may use submitted content, which here includes NID images and member data.

`python -m core.check_cloud` checks every model in the SQL and vision chains. `python3 -m ask_ai.check_models [provider/model ...]` (for example `ollama/gpt-oss:120b groq/openai/gpt-oss-120b`) ranks models on the 20 glossary examples: each question is left out of its own prompt examples and the generated result set is compared with the reference SQL on the DW. It costs about 20 calls per model.

Ollama Free provides starter usage with limits, not unlimited free cloud inference. Account access and quotas can change; no credits were purchased and no subscription was changed. The app does not automatically switch to a paid model. Older Qwen coder cloud tags returned HTTP 410 (retired), and the previously configured Qwen 3.5 397B returned HTTP 402 on this account. Existing SQL/report/scoring business logic is unchanged.

References: https://ollama.com/pricing and https://ollama.com/library/gemma4 . Restart Python processes after changing `.env` model names so inherited environment values are refreshed.
