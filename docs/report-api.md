# Group Performance Report API

The Python service reads month-end warehouse snapshots and calls Ollama Cloud.
A future .NET backend can proxy JSON and PDF bytes; no database or model key is
needed in the browser. Existing `/api/ask-ai` SQL/member responses remain compatible.

## Setup

Install `requirements.txt`. Configure server-side `OLLAMA_API_KEY` and the model
settings in `.env.example`. Cloud calls go directly to `https://ollama.com/api/chat`;
no Ollama daemon, model download, local GPU or EasyOCR fallback is used.
Qwen `qwen3.5:397b` serves text/SQL/report requests; `minimax-m3` serves vision.
Task overrides: `ASK_AI_MODEL`, `OLLAMA_MODEL`, `REPORT_AI_MODEL`, `OLLAMA_VISION_MODEL`.
Verify current availability with Ollama Cloud's `/api/tags` when changing models.

`REPORT_STORAGE_DIR` defaults to `data/reports` (gitignored). Use a persistent
volume shared by Python workers. Each report is an immutable JSON file identified
by a random ID; PDF downloads render that snapshot and never query fresh data.
Keep this API behind the same authenticated application gateway as warehouse Q&A;
report IDs are identifiers, not an authorization mechanism. The current application
does not implement tenant/user authorization. Do not expose it publicly unauthenticated.

## Requests

`POST /api/ask-ai` (also supported by the main chat endpoint `POST /api/ask`)

```json
{"question":"Group Performance Report August 2026","country":"ALL","summary":true}
```

`POST /api/reports/group-performance`

```json
{"period":"2026-08","country":"ALL","summary":true}
```

`period`: optional `YYYY-MM`. If omitted, selects the latest reconciled historical
month-end snapshot covering every selected country. Country: `UG`, `KY`, `TZ`,
`ZM`, or `ALL` (default). `summary:false` skips cloud evidence prioritization.
Current/future calendar months are rejected. A partial explicit historical month
can return available metrics and warnings. An empty source or failed connection
never yields a fabricated report.

Response: `{success:true, mode:"report", answer, report}`. The report contains
`schema_version:"1.0"`, `report_id`, `period`, `comparison_period`, `generated_at`,
`metrics`, `previous_metrics`, country metrics, `sections`, `sources`, `availability`,
`narrative_mode`, and `pdf_url`. Numbers are JSON numbers or `null`; percentages
are in percentage points (e.g. 2.14 means 2.14%, not 0.0214). Dates are ISO strings.
The presentation sections carry headings, paragraphs, blocks and string tables
shared with the PDF. Monetary comparisons use principal outstanding.

`GET /api/reports/{report_id}/pdf` returns `application/pdf` with attachment filename.
The relative PDF URL begins `/api/`; a .NET gateway may map it to its own route.
Use the same report ID to download exactly the previewed snapshot.

Errors: `{success:false, code, error}` with HTTP 400 (invalid input), 422 (period
selection/data missing), 404 (unknown report), 503 (warehouse/config unavailable).
Cloud narration failure falls back to evidence templates; financial tables remain
available. SQL generation requires cloud access and returns a clear failure when
unconfigured. Requests use bounded cloud retries; give the API caller a 180-second
request timeout. There is no background queue or polling API.

## Metric definitions and source limitations

- `MfCentralOutstandingReport`, exact month-end `TillDate`: `PrincipalOSTotal` and
  `TotalBorrowersTotal`. Count branches with positive principal. Use total-product
  fields only, not individual product subtotals. Reject duplicate country/branch keys.
- `MfCentralPortfolioAtRiskReport`: `PrincipalOSAbove30 / PrincipalAmount`.
  For each portfolio branch, require principal to reconcile with the outstanding
  snapshot and recomputed PAR to agree with the stored percentage to 0.02pp.
  Country and group ratios use summed risk amounts divided by summed principal.
- Monthly growth is `(current - previous) / previous * 100`. Zero/missing prior
  balance means unavailable. Local-currency country growth and USD group growth
  are explicitly distinguished. Group USD sums require FX for every country.
- Branch additions mean newly reporting portfolio branches, not proven opening dates.
- Dropout source rows are zero and the business denominator is unverified; report
  `null`, not zero. Historical borrower counts are source-reported counts.
- Readiness means reconciled month-end source coverage, not a business sign-off.
- The August sample has 214 portfolio branches while `MfTrendReport` contains
  219 distinct branch IDs across metrics. Central outstanding snapshots have 214
  rows (UG 99, KY 66, TZ 24, ZM 25). Do not count all trend rows as portfolio branches.
  Central Zambia borrowers differ from the supplied PDF; preserve the source value.
- `MfTrendReport.Principal` is populated for `Active Borrowers & Gross Loan
  Outstanding`; the old glossary claiming all monetary fields are zero was stale.

### Verified FX

Raw central `ForexRate` values include `1` placeholders for non-USD countries.
They are not used automatically. Set `REPORT_FX_FILE` to a JSON file containing
operator-verified **local currency units per USD**, keyed by month and country:

```json
{
  "2026-08": {
    "UG": {"local_per_usd": 3550, "source": "Example only: replace with approved month-end FX source"}
  }
}
```

The example is illustrative, not an approved rate. Add actual approved rates for
both report and comparison months, with source references. Without them local
figures remain available and USD figures are null. Changing FX affects new reports
only; previously generated snapshots remain unchanged.

## .NET HttpClient example

```csharp
using System.Net.Http.Json;
using System.Text.Json;

// Register via IHttpClientFactory in the host application.
services.AddHttpClient("MicrofinanceAI", client => {
    client.BaseAddress = new Uri("http://127.0.0.1:5001/");
    client.Timeout = TimeSpan.FromSeconds(180);
});

// In your application service/controller; propagate the caller cancellation token.
var client = httpClientFactory.CreateClient("MicrofinanceAI");
using var response = await client.PostAsJsonAsync("api/reports/group-performance",
    new { period = "2026-08", country = "ALL", summary = true }, cancellationToken);
// Forward the JSON body and HTTP status to the frontend, including error responses.
var body = await response.Content.ReadAsStringAsync(cancellationToken);
if (response.IsSuccessStatusCode) {
    using var parsed = JsonDocument.Parse(body);
    var id = parsed.RootElement.GetProperty("report").GetProperty("report_id").GetString();
    // In the separate PDF proxy action, use the saved ID requested by the frontend.
    using var pdfResponse = await client.GetAsync($"api/reports/{id}/pdf", cancellationToken);
    pdfResponse.EnsureSuccessStatusCode();
    byte[] pdf = await pdfResponse.Content.ReadAsByteArrayAsync(cancellationToken);
    // ASP.NET controller: return File(pdf, "application/pdf", "Group Performance Report.pdf");
}
```

The frontend's `VITE_API_BASE_URL` can point at the .NET gateway once implemented.
Keys, SQL access and report generation stay in Python. No .NET service is added here.

## Validation

Run `python -m unittest discover -s tests -v` and `npm run build` in `frontend`.
Use `python -m reports.verify_live --period 2026-08` for an explicit read-only DB
comparison and PDF sample. It uses no cloud narration and writes only generated
artifacts/snapshots. To validate cloud transport separately, use a configured key
and real approved SQL/document test samples; no identity documents are included.
