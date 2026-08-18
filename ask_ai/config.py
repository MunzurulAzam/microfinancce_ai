

import os

# DW — one MSSQL catalog holding all 4 countries (UG/KY/ZM/TZ).
# Credentials come from the environment; see .env.example.
DW_SERVER   = os.environ.get('DW_SERVER', '82.165.73.80')
DW_PORT     = int(os.environ.get('DW_PORT', 64928))
DW_USER     = os.environ.get('DW_USER', 'umissa')
DW_PASSWORD = os.environ.get('DW_PASSWORD', '')
DW_DATABASE = os.environ.get('DW_DATABASE', 'DW')

# Countries tagged on every DW row (MfMember.CountryCode etc.).
COUNTRY_CODES = ('UG', 'KY', 'ZM', 'TZ')

# Connecting costs ~2s, a query ~0.2s — so connections are pooled and reused.
POOL_SIZE = int(os.environ.get('ASK_AI_POOL_SIZE', 5))

# Client-side statement timeout. A timeout kills the connection, so the pool
# discards it rather than handing a dead socket to the next request.
QUERY_TIMEOUT = int(os.environ.get('ASK_AI_QUERY_TIMEOUT', 60))
LOGIN_TIMEOUT = int(os.environ.get('ASK_AI_LOGIN_TIMEOUT', 20))

# Never block a production writer waiting on a lock.
LOCK_TIMEOUT_MS = int(os.environ.get('ASK_AI_LOCK_TIMEOUT_MS', 5_000))

MAX_RESULT_ROWS = int(os.environ.get('ASK_AI_MAX_ROWS', 1000))

# Schema rarely changes; results are re-asked constantly.
SCHEMA_CACHE_TTL = int(os.environ.get('ASK_AI_SCHEMA_TTL', 3_600))
RESULT_CACHE_TTL = int(os.environ.get('ASK_AI_RESULT_TTL', 300))   # 0 disables

# Local Ollama model
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')

ASK_AI_MODEL = os.environ.get('ASK_AI_MODEL', 'qwen2.5:7b-instruct')

OLLAMA_KEEP_ALIVE = os.environ.get('ASK_AI_KEEP_ALIVE', '30m')

# DW has 132 tables — far too many for one prompt, and most are auth/menu/audit
# noise. Only these are described to the model and only these may be queried.
# AcVoucherMaster/AcVoucherDetail (44M/109M rows, clustered PK on DwId only) are
# deliberately excluded: any ad-hoc aggregate over them is a full scan.
TABLE_ALLOWLIST = (
    # Microfinance core
    'MfMember',
    'MfMemberAdditionalInfo',
    'MfMemberBusiness',
    'MfLoan',
    'MfLoanApplication',
    'MfLoanCollection',
    'MfLoanSchedule',
    'MfLoanProduct',
    'MfLoanGrantor',
    'MfLoanPurpose',
    'MfGroup',
    # Reporting / performance
    'MfTrendReport',
    'MfPerformanceTracker',
    'MfPerformanceTrackerData',
    'MfBadDebtsLoan',
    'MfBadDebtsCollection',
    # Accounting
    'AcFisTrialBalanceReportData',
    'AcLedger',
    'AcLedgerClassification',
    'AcBusinessDay',
    # HR / admin
    'HrEmployee',
    'HrDesignation',
    'HrDepartment',
    'AdBranch',
    'AdArea',
    'AdRegion',
    'AdDivision',
)

# Surrogate keys, image paths and GUIDs are never useful in an analytical answer;
# they only cost prompt tokens and invite mis-joins.
HIDDEN_COLUMNS = ('DwId', 'ImageUrl', 'IdImage', 'DisburseImage', 'GroupPhotoPath')
HIDDEN_COLUMN_SUFFIXES = ('Uid',)
