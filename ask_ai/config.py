

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

OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')

ASK_AI_MODEL = os.environ.get('ASK_AI_MODEL', 'qwen2.5:7b-instruct')

OLLAMA_KEEP_ALIVE = os.environ.get('ASK_AI_KEEP_ALIVE', '30m')


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
