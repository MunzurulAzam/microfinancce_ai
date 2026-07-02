

# Map spoken country names  the country code stored in every table.
COUNTRY_CODES = {
    'uganda':   'UG',
    'kenya':    'KY',
    'zambia':   'ZM',
    'tanzania': 'TZ',
}

GLOSSARY = """
KEY RULES
- Every table has a `country` column with values 'UG' (Uganda), 'KY' (Kenya),
  'ZM' (Zambia), 'TZ' (Tanzania). For a single-country question, filter on it,
  e.g. WHERE country = 'TZ'. For "all countries / combined / total", do NOT filter
  by country (optionally GROUP BY country to break it down).
- Join keys: MfLoan.MemberId = MfMember.MemberId;
  LoanCollectionSummary.LoanId = MfLoan.LoanId; MfMember.GroupId = MfGroup.GroupId;
  MfLoan.BranchId = AdBranch.BranchId; MfLoan.EmployeeId = HrEmployee.EmployeeId;
  CollectionMonthly.BranchId = AdBranch.BranchId;
  CollectionMonthly.EmployeeId = HrEmployee.EmployeeId.
  When joining across tables ALSO match country (a.country = b.country) because
  ids are only unique within a country.

DEFINITIONS
- Active member: MfMember.MemberStatus = 'Active'.
- Active loan: MfLoan.LoanStatus = 1.
- Loan portfolio: SUM(MfLoan.PrincipalAmount) where LoanStatus = 1.
- Outstanding amount: use MfLoan directly — PrincipalOutstanding,
  InterestOutstanding, TotalOutstanding (do NOT compute from collections).
- Collections are pre-aggregated (the raw per-installment table is not stored):
  * LoanCollectionSummary = one row per loan: TotalInstallments,
    OverdueInstallments, TotalOverdueAmount, TotalCollected,
    TotalPrincipalCollected, TotalInterestCollected, LastCollectionDate.
    Join to MfLoan on LoanId (+ country) to reach member/branch/officer/group.
  * CollectionMonthly = one row per branch+officer+month: TotalCollected,
    TotalOverdue, PrincipalCollected, InterestCollected, Installments,
    CollectionYear, CollectionMonth. Use this for collection trends over time.
- Overdue / arrears / PAR: a loan with LoanCollectionSummary.TotalOverdueAmount > 0
  (or OverdueInstallments > 0). Total overdue amount = SUM(TotalOverdueAmount).
- A client "with overdue" = a member whose loan has TotalOverdueAmount > 0.
- Total collected: SUM(LoanCollectionSummary.TotalCollected), or for a period use
  CollectionMonthly filtered by CollectionYear/CollectionMonth.
- Loan cycle: MfLoan.Cycle (1 = first loan, higher = repeat borrower).
- Loan officer (LO) = HrEmployee; branch = AdBranch.
- Member name = FirstName + ' ' + LastName.

ACCOUNTING / GL
- Trial balance / financial statements: AcFisTrialBalanceReportData, one row per
  ledger per month: LedgerCode, Year, Month, OpeningBalance, DebitTransaction,
  CreditTransaction, ClosingBalance. Join to AcLedger on LedgerCode to get
  LedgerName, AccountType, ClassificationName, ReportType (use ReportType /
  ClassificationName to split into Profit&Loss vs Balance Sheet). This is
  company-wide (no BranchId).

SAVINGS / DEPOSITS
- MfMemberDeposit: DepositId, MemberId, Amount, DepositDate, DepositStatus,
  LedgerId. Total savings = SUM(Amount). (May be empty in some countries.)
  Join to MfMember on MemberId (+ country).

DAILY COLLECTION & SCHEDULE
- CollectionDaily: actual collection per branch per day (CollectionDate,
  TotalCollected, TotalOverdue, ...). Use for daily / date-range collection reports.
- ScheduleMonthly: expected (due) installments per branch per month
  (ScheduleYear, ScheduleMonth, ExpectedInstallment, ...). Use for due /
  expected-vs-actual reports. Compare with CollectionMonthly for the same period.
- MfBadDebtsCollection: bad-debt recovery (collectionAmount, collectionDate,
  loanId). Note this table uses camelCase column names.
""".strip()

# Verified question -> SQL examples (few-shot). Written for DuckDB SQL.
EXAMPLES = [
    (
        "How many active members are there in Tanzania?",
        "SELECT COUNT(*) AS active_members\n"
        "FROM MfMember\n"
        "WHERE country = 'TZ' AND MemberStatus = 'Active';",
    ),
    (
        "What is the total loan portfolio across all countries?",
        "SELECT SUM(PrincipalAmount) AS total_portfolio\n"
        "FROM MfLoan\n"
        "WHERE LoanStatus = 1;",
    ),
    (
        "Show the active loan portfolio broken down by country.",
        "SELECT country, SUM(PrincipalAmount) AS portfolio, COUNT(*) AS active_loans\n"
        "FROM MfLoan\n"
        "WHERE LoanStatus = 1\n"
        "GROUP BY country\n"
        "ORDER BY portfolio DESC;",
    ),
    (
        "How many clients in Kenya have overdue payments?",
        "SELECT COUNT(DISTINCT l.MemberId) AS clients_with_overdue\n"
        "FROM MfLoan l\n"
        "JOIN LoanCollectionSummary s\n"
        "  ON s.LoanId = l.LoanId AND s.country = l.country\n"
        "WHERE l.country = 'KY' AND s.TotalOverdueAmount > 0;",
    ),
    (
        "Total overdue amount by branch in Uganda.",
        "SELECT b.BranchName, SUM(s.TotalOverdueAmount) AS overdue_amount\n"
        "FROM LoanCollectionSummary s\n"
        "JOIN MfLoan l ON s.LoanId = l.LoanId AND s.country = l.country\n"
        "JOIN AdBranch b ON l.BranchId = b.BranchId AND b.country = l.country\n"
        "WHERE s.country = 'UG'\n"
        "GROUP BY b.BranchName\n"
        "ORDER BY overdue_amount DESC;",
    ),
    (
        "Monthly collection trend for 2024 across all countries.",
        "SELECT CollectionYear, CollectionMonth, SUM(TotalCollected) AS collected\n"
        "FROM CollectionMonthly\n"
        "WHERE CollectionYear = 2024\n"
        "GROUP BY CollectionYear, CollectionMonth\n"
        "ORDER BY CollectionMonth;",
    ),
    (
        "Total outstanding portfolio by country.",
        "SELECT country, SUM(TotalOutstanding) AS outstanding\n"
        "FROM MfLoan\n"
        "WHERE LoanStatus = 1\n"
        "GROUP BY country\n"
        "ORDER BY outstanding DESC;",
    ),
    (
        "Which 5 branches in Uganda have the largest active loan portfolio?",
        "SELECT b.BranchName, SUM(l.PrincipalAmount) AS portfolio\n"
        "FROM MfLoan l\n"
        "JOIN AdBranch b ON b.BranchId = l.BranchId AND b.country = l.country\n"
        "WHERE l.country = 'UG' AND l.LoanStatus = 1\n"
        "GROUP BY b.BranchName\n"
        "ORDER BY portfolio DESC\n"
        "LIMIT 5;",
    ),
    (
        "Average loan size for female members in all countries.",
        "SELECT AVG(l.PrincipalAmount) AS avg_loan\n"
        "FROM MfLoan l\n"
        "JOIN MfMember m ON m.MemberId = l.MemberId AND m.country = l.country\n"
        "WHERE m.Gender = 'Female';",
    ),
    (
        "Trial balance for March 2024 in Uganda.",
        "SELECT t.LedgerCode, l.LedgerName, t.OpeningBalance,\n"
        "       t.DebitTransaction, t.CreditTransaction, t.ClosingBalance\n"
        "FROM AcFisTrialBalanceReportData t\n"
        "JOIN AcLedger l ON l.LedgerCode = t.LedgerCode AND l.country = t.country\n"
        "WHERE t.country = 'UG' AND t.Year = 2024 AND t.Month = 3\n"
        "ORDER BY t.LedgerCode;",
    ),
    (
        "Daily collection by branch for the last 7 days in Kenya.",
        "SELECT b.BranchName, d.CollectionDate, SUM(d.TotalCollected) AS collected\n"
        "FROM CollectionDaily d\n"
        "JOIN AdBranch b ON b.BranchId = d.BranchId AND b.country = d.country\n"
        "WHERE d.country = 'KY' AND d.CollectionDate >= CURRENT_DATE - INTERVAL 7 DAY\n"
        "GROUP BY b.BranchName, d.CollectionDate\n"
        "ORDER BY d.CollectionDate DESC;",
    ),
    (
        "Expected vs actual collection by month in 2024 (all countries).",
        "SELECT s.ScheduleYear AS yr, s.ScheduleMonth AS mon,\n"
        "       SUM(s.ExpectedInstallment) AS expected,\n"
        "       SUM(c.TotalCollected) AS actual\n"
        "FROM ScheduleMonthly s\n"
        "LEFT JOIN CollectionMonthly c\n"
        "  ON c.country = s.country AND c.BranchId = s.BranchId\n"
        "  AND c.CollectionYear = s.ScheduleYear AND c.CollectionMonth = s.ScheduleMonth\n"
        "WHERE s.ScheduleYear = 2024\n"
        "GROUP BY s.ScheduleYear, s.ScheduleMonth\n"
        "ORDER BY mon;",
    ),
    (
        "Total savings deposits by country.",
        "SELECT country, SUM(Amount) AS total_deposits, COUNT(*) AS deposit_count\n"
        "FROM MfMemberDeposit\n"
        "GROUP BY country\n"
        "ORDER BY total_deposits DESC;",
    ),
]


def examples_text():
    """Render the few-shot examples as a prompt block."""
    parts = []
    for q, sql in EXAMPLES:
        parts.append(f"-- Question: {q}\n{sql}")
    return "\n\n".join(parts)
