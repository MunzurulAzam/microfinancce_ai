

import re

from ask_ai.config import TABLE_ALLOWLIST

COUNTRY_CODES = {
    'uganda':   'UG',
    'kenya':    'KY',
    'zambia':   'ZM',
    'tanzania': 'TZ',
}

JOIN_RULES = """
WORDS THAT MEAN THE SAME THING
- member = client = customer = user = people = person. All of them mean a row in
  MfMember. Answer them identically.
- BORROWER is the one exception: it means a member who holds an active loan, so
  it needs MfLoan with LoanStatus = 1.
- loan officer = LO = officer = staff = employee -> HrEmployee.

HOW TABLES CONNECT  (there are no foreign keys — use exactly these paths)
- MfMember has NO BranchId and NO EmployeeId. Do not invent them.
  To reach a member's branch, go through the group:
      MfMember m
      JOIN MfGroup g  ON g.GroupId  = m.GroupId  AND g.CountryId = m.CountryId
      JOIN AdBranch b ON b.BranchId = g.BranchId AND b.CountryId = g.CountryId
- MfLoan DOES carry BranchId, EmployeeId and GroupId directly. Use MfLoan when
  the question is about loans, borrowers, disbursement or collections.
- MfGroup carries BranchId and EmployeeId. HrEmployee carries BranchId.
- MfLoanCollection / MfLoanSchedule reach a branch only via MfLoan.
- Branch hierarchy: AdBranch.AreaId -> AdArea -> AdRegion -> AdDivision.
- "Members of a branch" and "borrowers of a branch" are different numbers.
  When a question asks about a branch's members, report BOTH: members via the
  group path, and active borrowers via the loan path.
- Those two counts are at DIFFERENT grains, so compute each in its OWN
  subquery selected FROM AdBranch. Do NOT try to get both from one query that
  LEFT JOINs MfLoan: putting l.LoanStatus = 1 in the WHERE clause turns the
  LEFT JOIN into an INNER JOIN, members without a loan disappear, and both
  counts silently collapse to the same wrong number.
- Generally: a condition on a LEFT JOINed table belongs in the ON clause, never
  in WHERE.
- If the question names a branch, filter it: WHERE b.BranchName = 'Nyangusu'.
  Only group over all branches when the question asks to compare branches.
- Every one of these joins must also match CountryId.
""".strip()

_GLOSSARY_TEMPLATE = """
DIALECT
- This is Microsoft SQL Server (T-SQL). Use TOP (n), never LIMIT.
- Row limit: SELECT TOP (100) ... . Ranking: ORDER BY ... with TOP.
- String concat is + (use CONCAT() when a value may be NULL). Not ||.
- Date maths: DATEADD(day, -30, x), DATEDIFF(day, a, b), YEAR(x), MONTH(x),
  CAST(x AS date). There is no INTERVAL keyword.
- LIKE is already case-insensitive here. Never use ILIKE.

KEY RULES
- DW holds all 4 countries in ONE database. Every table has CountryId (int) and
  CountryCode (nvarchar): 'UG' Uganda, 'KY' Kenya, 'ZM' Zambia, 'TZ' Tanzania.
  Single country -> WHERE CountryCode = 'TZ'.
  "All countries / combined / total" -> do NOT filter; add GROUP BY CountryCode
  when a per-country breakdown is useful.
- Business ids (LoanId, MemberId, BranchId, GroupId, EmployeeId) are only unique
  WITHIN a country. EVERY join must also match the country:
      JOIN MfMember m ON m.MemberId = l.MemberId AND m.CountryId = l.CountryId
  Omitting CountryId silently multiplies rows across countries and every total
  comes out wrong.

{JOIN_RULES}

LOAN STATUS  (this is the most common source of wrong answers)
- MfLoan.LoanStatus: 1 = active/running, 2 and 3 = closed/completed,
  4 = rare/other, 5 = bad debt (written off).
- MfLoan.TotalOutstanding / PrincipalOutstanding / InterestOutstanding are NOT
  reset to zero when a loan closes — closed loans keep their last snapshot.
  So ANY portfolio, outstanding or active-loan figure MUST filter LoanStatus = 1.
  Without that filter the total is roughly 5x too large.

JOIN ONLY WHAT YOU NEED
- Never join a table you take no column from. Joining MfMember to MfLoan silently
  changes "how many members" into "how many members hold a loan" — a different,
  smaller number. Count members from MfMember alone.

DEFINITIONS
- Active member: MfMember.MemberStatus = 'Active', counted from MfMember on its
  own with NO join to MfLoan. Other statuses: 'Inactive', 'Deleted', 'Rejected',
  'Deceased', 'Pending'.
- Active borrower / member with a loan: that is a DIFFERENT question — join
  MfLoan and filter LoanStatus = 1. Only do this when the question actually asks
  about loans or borrowers.
- Active loan: MfLoan.LoanStatus = 1 (count rows in MfLoan, not members).
- Outstanding portfolio: SUM(MfLoan.TotalOutstanding) WHERE LoanStatus = 1.
  Principal only: SUM(PrincipalOutstanding) WHERE LoanStatus = 1.
- Disbursed amount: SUM(MfLoan.PrincipalAmount), filtered by DisburseDate for a
  period. This is a flow (what was lent), unlike outstanding which is a balance.
- Loan cycle: MfLoan.Cycle (1 = first loan, higher = repeat borrower).
- Member name: FirstName + ' ' + LastName. Member code: MfMember.MemberCode
  (looks like 'CLN123456'). Loan reference: MfLoan.LoanNo.
- Loan officer (LO) = HrEmployee.EmployeeName via MfLoan.EmployeeId.
  Branch = AdBranch.BranchName via MfLoan.BranchId.
  Group = MfGroup.GroupName via MfMember.GroupId or MfLoan.GroupId.
- Branch hierarchy: AdBranch.AreaId -> AdArea -> AdRegion -> AdDivision.
- Nearly all members are Female — a gender split is rarely the interesting cut.

COLLECTIONS AND ARREARS  (MfLoanCollection, one row per installment event)
- Columns: WorkDate, LoanId, CollectionAmount, PrincipalRelized, InterestRelized,
  OverdueAmount, OverduePrincipal, OverdueInterest, InstallmentAmount,
  TargateAmount, OutstandingAmount, IsNewOverdue, CollectionBehaviour.
  NOTE the spellings "Relized" and "Targate" — they are misspelled in the schema.
- Amount collected in a period: SUM(CollectionAmount) filtered on WorkDate.
- Overdue / arrears / PAR: an installment with OverdueAmount > 0. A loan is in
  arrears if it has any such row. Total overdue = SUM(OverdueAmount).
- This table has 20M+ rows. Always constrain it — by WorkDate range, by
  CountryCode, or by joining to a filtered set of loans.
- Latest data available: use (SELECT MAX(WorkDate) FROM MfLoanCollection) as
  "today" rather than GETDATE(); the warehouse lags the live system.

SCHEDULE  (MfLoanSchedule, the expected/due side, 23M rows)
- Columns: PaymentDate, LoanId, InstallmentAmount, PrincipalRealized,
  InterestRealized, PrincipalOutstanding, InterestOutstanding,
  ClosingOutstanding, InstallmentNo.
  NOTE: spelled "Realized" here, but "Relized" in MfLoanCollection.
- Expected vs actual: compare SUM(MfLoanSchedule.InstallmentAmount) for a period
  against SUM(MfLoanCollection.CollectionAmount) for the same period.

BAD DEBT
- MfBadDebtsLoan: LoanId, MemberId, BranchId, BadDebtPrincOS, BadDebtIntOS,
  BadDebtTotalOS, OverDueAging, LastCollectionDate, Status. These are the
  written-off loans (they also carry MfLoan.LoanStatus = 5).
- MfBadDebtsCollection = recovery against written-off loans. This table uses
  camelCase: loanId, collectionAmount, collectionDate, collectionBehaviour,
  status, InterestAmt, PrincipalAmt.

PRE-AGGREGATED REPORTING
- MfTrendReport: monthly per branch, keyed by Matrix (the metric name), with
  ReportYear, ReportMonth, BranchId, ProductShortName. Two shapes of row:
  * Matrix = 'PAR Status (All Loans)' -> the ageing buckets PrincipalOS0,
    PrincipalOS30, PrincipalOSAbove30, PrincipalOS180, PrincipalOS365. Use these
    for PAR. On these rows Nos is 0.
  * Every other Matrix (e.g. 'Active Members Female', 'Number of Active Group',
    'Number of Branch', 'Add: Admission (this month)', 'UML') -> the value is in
    Nos. On these rows the PrincipalOS* columns are 0.
  The columns TotalOutStanding, Principal, WithInterest and Amount are always 0
  in this table — never select them. For an outstanding figure use MfLoan
  (LoanStatus = 1) instead.
  The most recent month is usually partial; exclude it for a clean trend.
- MfPerformanceTrackerData: daily per officer/branch. BusinessDate, BranchId,
  LOName, BMName, AMName, NoOfNewAdmission, NoOfTotalDisburse,
  TotalDisbursementAmount, TotalCollection, BadDebtCollection.

ACCOUNTING / GL
- AcFisTrialBalanceReportData: one row per ledger per month. LedgerCode, Year,
  Month, Nature, OpeningBalance, DebitTransaction, CreditTransaction,
  ClosingBalance. Nature is 'Assets', 'Liabilities', 'Incomes' or 'Expenses' —
  use it to split balance sheet from profit & loss.
- Join AcLedger on LedgerCode (+ CountryId) for LedgerName, AccountType
  ('General', 'Bank', 'Cash') and ClassificationName (e.g. 'Gross Loan
  portfolio', 'Salaries and Wages'). AcLedger.ReportType is mostly 'N/A' —
  do not use it to classify accounts.
"""

GLOSSARY = _GLOSSARY_TEMPLATE.strip().format(JOIN_RULES=JOIN_RULES)


METRIC_CTES = """
REUSABLE BUILDING BLOCKS — copy these verbatim when the question needs them.

-- Per-loan collection history (arrears, repayment behaviour):
WITH LoanCollectionSummary AS (
    SELECT CountryId, CountryCode, LoanId,
           COUNT(*)                                              AS TotalInstallments,
           SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END)    AS OverdueInstallments,
           SUM(OverdueAmount)                                    AS TotalOverdueAmount,
           SUM(CollectionAmount)                                 AS TotalCollected,
           SUM(PrincipalRelized)                                 AS TotalPrincipalCollected,
           SUM(InterestRelized)                                  AS TotalInterestCollected,
           MAX(WorkDate)                                         AS LastCollectionDate
    FROM MfLoanCollection
    GROUP BY CountryId, CountryCode, LoanId
)

-- Collection per branch per month (trends). Filter WorkDate first — the source
-- table has 20M+ rows:
WITH CollectionMonthly AS (
    SELECT l.CountryId, l.CountryCode, l.BranchId, l.EmployeeId,
           YEAR(c.WorkDate)        AS CollectionYear,
           MONTH(c.WorkDate)       AS CollectionMonth,
           SUM(c.CollectionAmount) AS TotalCollected,
           SUM(c.OverdueAmount)    AS TotalOverdue,
           SUM(c.PrincipalRelized) AS PrincipalCollected,
           SUM(c.InterestRelized)  AS InterestCollected,
           COUNT(*)                AS Installments
    FROM MfLoanCollection c
    JOIN MfLoan l ON l.LoanId = c.LoanId AND l.CountryId = c.CountryId
    WHERE c.WorkDate >= '2025-01-01'
    GROUP BY l.CountryId, l.CountryCode, l.BranchId, l.EmployeeId,
             YEAR(c.WorkDate), MONTH(c.WorkDate)
)

-- Expected installments per branch per month (due side):
WITH ScheduleMonthly AS (
    SELECT l.CountryId, l.CountryCode, l.BranchId,
           YEAR(s.PaymentDate)          AS ScheduleYear,
           MONTH(s.PaymentDate)         AS ScheduleMonth,
           SUM(s.InstallmentAmount)     AS ExpectedInstallment,
           SUM(s.PrincipalRealized)     AS PrincipalRealized,
           SUM(s.InterestRealized)      AS InterestRealized,
           COUNT(*)                     AS Installments
    FROM MfLoanSchedule s
    JOIN MfLoan l ON l.LoanId = s.LoanId AND l.CountryId = s.CountryId
    WHERE s.PaymentDate >= '2025-01-01'
    GROUP BY l.CountryId, l.CountryCode, l.BranchId,
             YEAR(s.PaymentDate), MONTH(s.PaymentDate)
)
""".strip()


# check_examples.py runs every one of these — a broken example teaches the model to be wrong.
EXAMPLES = [
    (
        "How many active members are there in Tanzania?",
        "SELECT COUNT(*) AS active_members\n"
        "FROM MfMember\n"
        "WHERE CountryCode = 'TZ' AND MemberStatus = 'Active';",
    ),
    (
        "How many active members are there in each country?",
        "SELECT CountryCode, COUNT(*) AS active_members\n"
        "FROM MfMember\n"
        "WHERE MemberStatus = 'Active'\n"
        "GROUP BY CountryCode\n"
        "ORDER BY active_members DESC;",
    ),
    (
        "Give me the total members of Nyangusu branch",
        "SELECT b.BranchName, b.CountryCode,\n"
        "       (SELECT COUNT(*) FROM MfMember m\n"
        "          JOIN MfGroup g ON g.GroupId = m.GroupId AND g.CountryId = m.CountryId\n"
        "         WHERE g.BranchId = b.BranchId AND g.CountryId = b.CountryId\n"
        "           AND m.MemberStatus = 'Active')          AS active_members,\n"
        "       (SELECT COUNT(DISTINCT l.MemberId) FROM MfLoan l\n"
        "         WHERE l.BranchId = b.BranchId AND l.CountryId = b.CountryId\n"
        "           AND l.LoanStatus = 1)                   AS active_borrowers\n"
        "FROM AdBranch b\n"
        "WHERE b.BranchName = 'Nyangusu';",
    ),
    (
        "List the member names in Nyangusu branch",
        "SELECT TOP (100) m.MemberCode, m.FirstName + ' ' + m.LastName AS member_name\n"
        "FROM MfMember m\n"
        "JOIN MfGroup g  ON g.GroupId  = m.GroupId  AND g.CountryId = m.CountryId\n"
        "JOIN AdBranch b ON b.BranchId = g.BranchId AND b.CountryId = g.CountryId\n"
        "WHERE b.BranchName = 'Nyangusu' AND m.MemberStatus = 'Active'\n"
        "ORDER BY member_name;",
    ),
    (
        "Which branches have the most members?",
        "SELECT TOP (10) b.BranchName, b.CountryCode, COUNT(*) AS active_members\n"
        "FROM MfMember m\n"
        "JOIN MfGroup g  ON g.GroupId  = m.GroupId  AND g.CountryId = m.CountryId\n"
        "JOIN AdBranch b ON b.BranchId = g.BranchId AND b.CountryId = g.CountryId\n"
        "WHERE m.MemberStatus = 'Active'\n"
        "GROUP BY b.BranchName, b.CountryCode\n"
        "ORDER BY active_members DESC;",
    ),
    (
        "How many active borrowers (members holding an active loan) are there in each country?",
        "SELECT l.CountryCode, COUNT(DISTINCT l.MemberId) AS active_borrowers\n"
        "FROM MfLoan l\n"
        "WHERE l.LoanStatus = 1\n"
        "GROUP BY l.CountryCode\n"
        "ORDER BY active_borrowers DESC;",
    ),
    (
        "What is the total outstanding loan portfolio across all countries?",
        "SELECT SUM(TotalOutstanding) AS total_outstanding\n"
        "FROM MfLoan\n"
        "WHERE LoanStatus = 1;",
    ),
    (
        "Show the active loan portfolio broken down by country.",
        "SELECT CountryCode,\n"
        "       COUNT(*) AS active_loans,\n"
        "       SUM(PrincipalAmount) AS disbursed,\n"
        "       SUM(TotalOutstanding) AS outstanding\n"
        "FROM MfLoan\n"
        "WHERE LoanStatus = 1\n"
        "GROUP BY CountryCode\n"
        "ORDER BY outstanding DESC;",
    ),
    (
        "How many clients in Kenya have overdue payments?",
        "SELECT COUNT(DISTINCT l.MemberId) AS clients_with_overdue\n"
        "FROM MfLoan l\n"
        "JOIN MfLoanCollection c\n"
        "  ON c.LoanId = l.LoanId AND c.CountryId = l.CountryId\n"
        "WHERE l.CountryCode = 'KY' AND l.LoanStatus = 1 AND c.OverdueAmount > 0;",
    ),
    (
        "Total overdue amount by branch in Uganda.",
        "SELECT b.BranchName, SUM(c.OverdueAmount) AS overdue_amount\n"
        "FROM MfLoanCollection c\n"
        "JOIN MfLoan l ON l.LoanId = c.LoanId AND l.CountryId = c.CountryId\n"
        "JOIN AdBranch b ON b.BranchId = l.BranchId AND b.CountryId = l.CountryId\n"
        "WHERE l.CountryCode = 'UG' AND l.LoanStatus = 1 AND c.OverdueAmount > 0\n"
        "GROUP BY b.BranchName\n"
        "ORDER BY overdue_amount DESC;",
    ),
    (
        "Monthly collection trend for 2025 across all countries.",
        "SELECT YEAR(WorkDate) AS collection_year,\n"
        "       MONTH(WorkDate) AS collection_month,\n"
        "       SUM(CollectionAmount) AS collected\n"
        "FROM MfLoanCollection\n"
        "WHERE WorkDate >= '2025-01-01' AND WorkDate < '2026-01-01'\n"
        "GROUP BY YEAR(WorkDate), MONTH(WorkDate)\n"
        "ORDER BY collection_year, collection_month;",
    ),
    (
        "Which 5 branches in Uganda have the largest active loan portfolio?",
        "SELECT TOP (5) b.BranchName, SUM(l.TotalOutstanding) AS outstanding\n"
        "FROM MfLoan l\n"
        "JOIN AdBranch b ON b.BranchId = l.BranchId AND b.CountryId = l.CountryId\n"
        "WHERE l.CountryCode = 'UG' AND l.LoanStatus = 1\n"
        "GROUP BY b.BranchName\n"
        "ORDER BY outstanding DESC;",
    ),
    (
        "Average loan size for female members in all countries.",
        "SELECT l.CountryCode, AVG(l.PrincipalAmount) AS avg_loan\n"
        "FROM MfLoan l\n"
        "JOIN MfMember m ON m.MemberId = l.MemberId AND m.CountryId = l.CountryId\n"
        "WHERE m.Gender = 'Female' AND l.LoanStatus = 1\n"
        "GROUP BY l.CountryCode\n"
        "ORDER BY avg_loan DESC;",
    ),
    (
        "Top 10 loan officers in Uganda by amount collected in 2025.",
        "SELECT TOP (10) e.EmployeeName, SUM(c.CollectionAmount) AS collected\n"
        "FROM MfLoanCollection c\n"
        "JOIN MfLoan l ON l.LoanId = c.LoanId AND l.CountryId = c.CountryId\n"
        "JOIN HrEmployee e ON e.EmployeeId = l.EmployeeId AND e.CountryId = l.CountryId\n"
        "WHERE l.CountryCode = 'UG'\n"
        "  AND c.WorkDate >= '2025-01-01' AND c.WorkDate < '2026-01-01'\n"
        "GROUP BY e.EmployeeName\n"
        "ORDER BY collected DESC;",
    ),
    (
        "Trial balance for March 2026 in Uganda.",
        "SELECT t.LedgerCode, l.LedgerName, t.Nature, t.OpeningBalance,\n"
        "       t.DebitTransaction, t.CreditTransaction, t.ClosingBalance\n"
        "FROM AcFisTrialBalanceReportData t\n"
        "JOIN AcLedger l ON l.LedgerCode = t.LedgerCode AND l.CountryId = t.CountryId\n"
        "WHERE t.CountryCode = 'UG' AND t.Year = 2026 AND t.Month = 3\n"
        "ORDER BY t.LedgerCode;",
    ),
    (
        "Daily collection by branch for the last 7 days in Kenya.",
        "SELECT b.BranchName, CAST(c.WorkDate AS date) AS collection_date,\n"
        "       SUM(c.CollectionAmount) AS collected\n"
        "FROM MfLoanCollection c\n"
        "JOIN MfLoan l ON l.LoanId = c.LoanId AND l.CountryId = c.CountryId\n"
        "JOIN AdBranch b ON b.BranchId = l.BranchId AND b.CountryId = l.CountryId\n"
        "WHERE c.CountryCode = 'KY'\n"
        "  AND c.WorkDate >= DATEADD(day, -7, (SELECT MAX(WorkDate) FROM MfLoanCollection))\n"
        "GROUP BY b.BranchName, CAST(c.WorkDate AS date)\n"
        "ORDER BY collection_date DESC, collected DESC;",
    ),
    (
        "Expected vs actual collection by month in 2025 for Uganda.",
        "WITH expected AS (\n"
        "    SELECT YEAR(s.PaymentDate) AS yr, MONTH(s.PaymentDate) AS mon,\n"
        "           SUM(s.InstallmentAmount) AS expected_amount\n"
        "    FROM MfLoanSchedule s\n"
        "    WHERE s.CountryCode = 'UG'\n"
        "      AND s.PaymentDate >= '2025-01-01' AND s.PaymentDate < '2026-01-01'\n"
        "    GROUP BY YEAR(s.PaymentDate), MONTH(s.PaymentDate)\n"
        "), actual AS (\n"
        "    SELECT YEAR(c.WorkDate) AS yr, MONTH(c.WorkDate) AS mon,\n"
        "           SUM(c.CollectionAmount) AS actual_amount\n"
        "    FROM MfLoanCollection c\n"
        "    WHERE c.CountryCode = 'UG'\n"
        "      AND c.WorkDate >= '2025-01-01' AND c.WorkDate < '2026-01-01'\n"
        "    GROUP BY YEAR(c.WorkDate), MONTH(c.WorkDate)\n"
        ")\n"
        "SELECT e.yr, e.mon, e.expected_amount, a.actual_amount\n"
        "FROM expected e\n"
        "LEFT JOIN actual a ON a.yr = e.yr AND a.mon = e.mon\n"
        "ORDER BY e.yr, e.mon;",
    ),
    (
        "Total bad debt outstanding by country.",
        "SELECT CountryCode,\n"
        "       COUNT(*) AS bad_debt_loans,\n"
        "       SUM(BadDebtTotalOS) AS bad_debt_outstanding\n"
        "FROM MfBadDebtsLoan\n"
        "GROUP BY CountryCode\n"
        "ORDER BY bad_debt_outstanding DESC;",
    ),
    (
        "How many new members were admitted in each country in 2025?",
        "SELECT CountryCode, COUNT(*) AS new_members\n"
        "FROM MfMember\n"
        "WHERE AdmissionDate >= '2025-01-01' AND AdmissionDate < '2026-01-01'\n"
        "GROUP BY CountryCode\n"
        "ORDER BY new_members DESC;",
    ),
    (
        "Show the PAR ageing buckets by country for the latest full month.",
        "SELECT CountryCode, ReportYear, ReportMonth,\n"
        "       SUM(PrincipalOS0) AS par_0,\n"
        "       SUM(PrincipalOS30) AS par_30,\n"
        "       SUM(PrincipalOSAbove30) AS par_above_30,\n"
        "       SUM(PrincipalOS180) AS par_180,\n"
        "       SUM(PrincipalOS365) AS par_365\n"
        "FROM MfTrendReport\n"
        "WHERE Matrix = 'PAR Status (All Loans)'\n"
        "  AND ReportYear = 2026 AND ReportMonth = 6\n"
        "GROUP BY CountryCode, ReportYear, ReportMonth\n"
        "ORDER BY CountryCode;",
    ),
]


def _tables_used(sql):
    return frozenset(t for t in TABLE_ALLOWLIST
                     if re.search(rf'\b{t}\b', sql))


_EXAMPLE_TABLES = [_tables_used(sql) for _, sql in EXAMPLES]

_ANCHOR_EXAMPLES = 2


def examples_text(tables=None, limit=8):
    if not tables:
        chosen = range(len(EXAMPLES))
    else:
        wanted = set(tables)
        chosen = [i for i, used in enumerate(_EXAMPLE_TABLES)
                  if i < _ANCHOR_EXAMPLES or (used & wanted)]
        if len(chosen) > limit:
            # Drop the least relevant first, but never reorder.
            ranked = sorted(
                chosen[_ANCHOR_EXAMPLES:],
                key=lambda i: len(_EXAMPLE_TABLES[i] & wanted),
                reverse=True,
            )
            keep = set(list(range(_ANCHOR_EXAMPLES)) + ranked[:limit - _ANCHOR_EXAMPLES])
            chosen = [i for i in chosen if i in keep]

    return "\n\n".join(f"-- Question: {EXAMPLES[i][0]}\n{EXAMPLES[i][1]}"
                        for i in chosen)
