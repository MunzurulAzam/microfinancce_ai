

import os

# Shared MSSQL credentials
_SERVER   = os.environ.get('MSSQL_SERVER', '192.129.248.10')
_PORT     = int(os.environ.get('MSSQL_PORT', 1543))
_USER     = os.environ.get('MSSQL_USER', 'umissa')
_PASSWORD = os.environ.get('MSSQL_PASSWORD', 'm9X3f1S>C6@:E)BI')


def _profile(country, default_db, env_key):
    """Build one connection profile; the catalog is env-overridable per country."""
    return {
        'country':  country,
        'server':   _SERVER,
        'port':     _PORT,
        'user':     _USER,
        'password': _PASSWORD,
        'database': os.environ.get(env_key, default_db),
    }


#  4 country profiles
COUNTRIES = [
    _profile('UG', 'db_UMISv2_ug', 'MSSQL_DB_UG'),   # Uganda
    _profile('KY', 'db_UMISv2_KY', 'MSSQL_DB_KY'),   # Kenya
    _profile('ZM', 'db_UMISv2_zm', 'MSSQL_DB_ZM'),   # Zambia
    _profile('TZ', 'db_UMISv2_Tz', 'MSSQL_DB_TZ'),   # Tanzania
]


COUNTRIES_BY_CODE = {p['country']: p for p in COUNTRIES}


SYNC_TABLES = [
    'MfMember',
    'MfLoan',
    'MfGroup',
    'AdBranch',
    'HrEmployee',
    'MfMemberBusiness',
    'MfMemberAdditionalInfo',
    'MfLoanGrantor',

    'AcLedger',
    'AcFisTrialBalanceReportData',
    'MfMemberDeposit',
    'MfBadDebtsCollection',
]

#  Derived server-side aggregated tables

DERIVED_TABLES = [
    {
        'name': 'LoanCollectionSummary',   # one row per loan
        'key': 'LoanId',                    # keyset-paginated GROUP BY: bounded pages, resumable
        'requires': ['MfLoanCollection'],
        'select': (
            'LoanId, '
            'COUNT(*) AS TotalInstallments, '
            'SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END) AS OverdueInstallments, '
            'SUM(OverdueAmount) AS TotalOverdueAmount, '
            'SUM(CollectionAmount) AS TotalCollected, '
            'SUM(PrincipalRelized) AS TotalPrincipalCollected, '
            'SUM(InterestRelized) AS TotalInterestCollected, '
            'MAX(WorkDate) AS LastCollectionDate'
        ),
        'from': 'MfLoanCollection',
        'group_by': 'LoanId',
    },
    {
        'name': 'CollectionMonthly',        # collection trend, coarse (small)
        'key': None,
        'chunk_col': 'c.WorkDate',          # aggregate one year at a time: bounded queries
        'chunk_from': 'MfLoanCollection c',
        'requires': ['MfLoanCollection', 'MfLoan'],
        'select': (
            'l.BranchId, l.EmployeeId, '
            'YEAR(c.WorkDate) AS CollectionYear, '
            'MONTH(c.WorkDate) AS CollectionMonth, '
            'SUM(c.CollectionAmount) AS TotalCollected, '
            'SUM(c.OverdueAmount) AS TotalOverdue, '
            'SUM(c.PrincipalRelized) AS PrincipalCollected, '
            'SUM(c.InterestRelized) AS InterestCollected, '
            'COUNT(*) AS Installments'
        ),
        'from': 'MfLoanCollection c JOIN MfLoan l ON c.LoanId = l.LoanId',
        'group_by': 'l.BranchId, l.EmployeeId, YEAR(c.WorkDate), MONTH(c.WorkDate)',
    },
    {
        'name': 'CollectionDaily',          # daily collection per branch (date-range reports)
        'key': None,
        'chunk_col': 'c.WorkDate',
        'chunk_from': 'MfLoanCollection c',
        'requires': ['MfLoanCollection', 'MfLoan'],
        'select': (
            'l.BranchId, '
            'CAST(c.WorkDate AS date) AS CollectionDate, '
            'SUM(c.CollectionAmount) AS TotalCollected, '
            'SUM(c.OverdueAmount) AS TotalOverdue, '
            'SUM(c.PrincipalRelized) AS PrincipalCollected, '
            'SUM(c.InterestRelized) AS InterestCollected, '
            'COUNT(*) AS Installments'
        ),
        'from': 'MfLoanCollection c JOIN MfLoan l ON c.LoanId = l.LoanId',
        'group_by': 'l.BranchId, CAST(c.WorkDate AS date)',
    },
    {
        'name': 'ScheduleMonthly',          # expected installments (due) per branch per month
        'key': None,
        'chunk_col': 's.PaymentDate',
        'chunk_from': 'MfLoanSchedule s',
        'requires': ['MfLoanSchedule', 'MfLoan'],
        'select': (
            'l.BranchId, '
            'YEAR(s.PaymentDate) AS ScheduleYear, '
            'MONTH(s.PaymentDate) AS ScheduleMonth, '
            'SUM(s.InstallmentAmount) AS ExpectedInstallment, '
            'SUM(s.PrincipalRealized) AS PrincipalRealized, '
            'SUM(s.InterestRealized) AS InterestRealized, '
            'COUNT(*) AS Installments'
        ),
        'from': 'MfLoanSchedule s JOIN MfLoan l ON s.LoanId = l.LoanId',
        'group_by': 'l.BranchId, YEAR(s.PaymentDate), MONTH(s.PaymentDate)',
    },
]

# Local warehouse a single DuckDB file ─
_THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(_THIS_DIR, 'data')
WAREHOUSE_PATH = os.environ.get('ASK_AI_WAREHOUSE', os.path.join(DATA_DIR, 'warehouse.duckdb'))


SYNC_BATCH_SIZE = int(os.environ.get('ASK_AI_SYNC_BATCH', 5_000))


# page-level retry reconnects and re-issues just that page.
SYNC_QUERY_TIMEOUT = int(os.environ.get('ASK_AI_QUERY_TIMEOUT', 1_800))

# Whole-table retries (outer loop) — kept as a last resort.
SYNC_RETRIES = int(os.environ.get('ASK_AI_SYNC_RETRIES', 3))

# Per-page retries: a dropped connection costs one page, not the whole table.
SYNC_PAGE_RETRIES = int(os.environ.get('ASK_AI_PAGE_RETRIES', 5))

# Local Ollama model
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')


ASK_AI_MODEL    = os.environ.get('ASK_AI_MODEL', 'qwen2.5:7b-instruct')

OLLAMA_KEEP_ALIVE = os.environ.get('ASK_AI_KEEP_ALIVE', '30m')


MAX_RESULT_ROWS = int(os.environ.get('ASK_AI_MAX_ROWS', 1000))
