

import os

DW_SERVER   = os.environ.get('DW_SERVER', '82.165.73.80')
DW_PORT     = int(os.environ.get('DW_PORT', 64928))
DW_USER     = os.environ.get('DW_USER', 'umissa')
DW_PASSWORD = os.environ.get('DW_PASSWORD', '')
DW_DATABASE = os.environ.get('DW_DATABASE', 'DW')

COUNTRY_CODES = ('UG', 'KY', 'ZM', 'TZ')


POOL_SIZE = int(os.environ.get('ASK_AI_POOL_SIZE', 5))

QUERY_TIMEOUT = int(os.environ.get('ASK_AI_QUERY_TIMEOUT', 60))
LOGIN_TIMEOUT = int(os.environ.get('ASK_AI_LOGIN_TIMEOUT', 20))

LOCK_TIMEOUT_MS = int(os.environ.get('ASK_AI_LOCK_TIMEOUT_MS', 5_000))

MAX_RESULT_ROWS = int(os.environ.get('ASK_AI_MAX_ROWS', 1000))

SCHEMA_CACHE_TTL = int(os.environ.get('ASK_AI_SCHEMA_TTL', 3_600))
RESULT_CACHE_TTL = int(os.environ.get('ASK_AI_RESULT_TTL', 300))

TABLE_ALLOWLIST = (
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
    'MfTrendReport',
    'MfPerformanceTracker',
    'MfPerformanceTrackerData',
    'MfBadDebtsLoan',
    'MfBadDebtsCollection',
    'AcFisTrialBalanceReportData',
    'AcLedger',
    'AcLedgerClassification',
    'AcBusinessDay',
    'HrEmployee',
    'HrDesignation',
    'HrDepartment',
    'AdBranch',
    'AdArea',
    'AdRegion',
    'AdDivision',
)

# Surrogate keys, image paths and GUIDs cost prompt tokens and invite mis-joins.
HIDDEN_COLUMNS = ('DwId', 'ImageUrl', 'IdImage', 'DisburseImage', 'GroupPhotoPath')
HIDDEN_COLUMN_SUFFIXES = ('Uid',)

# ── Dify external knowledge API ──────────────────────────────────────────────
# Dify calls POST /api/dify/retrieval with a Bearer key and one of these ids.
DIFY_KB_API_KEY   = os.environ.get('DIFY_KB_API_KEY', '')
DIFY_LIVE_KB_ID   = os.environ.get('DIFY_LIVE_KB_ID', 'dw-live')
DIFY_SCHEMA_KB_ID = os.environ.get('DIFY_SCHEMA_KB_ID', 'dw-schema')

DIFY_MAX_TOP_K = int(os.environ.get('DIFY_MAX_TOP_K', 10))

# Rows rendered into a record — the whole record has to fit an LLM context.
DIFY_TABLE_ROWS = int(os.environ.get('DIFY_TABLE_ROWS', 50))
