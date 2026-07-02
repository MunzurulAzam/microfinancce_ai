

import os
import re

import duckdb
import requests

from ask_ai.config import (
    OLLAMA_BASE_URL,
    ASK_AI_MODEL,
    OLLAMA_KEEP_ALIVE,
    WAREHOUSE_PATH,
    MAX_RESULT_ROWS,
)
from ask_ai import schema as schema_mod
from ask_ai.glossary import GLOSSARY, examples_text


#  Relevant-table selection

_CORE_TABLES = ['MfMember', 'MfLoan']
_TABLE_KEYWORDS = {
    'MfMember':               ['member', 'client', 'customer', 'borrower', 'people',
                               'women', 'woman', 'female', 'men', 'male', 'gender', 'age'],
    'MfLoan':                 ['loan', 'portfolio', 'principal', 'disburse', 'cycle',
                               'amount', 'outstanding'],
    'LoanCollectionSummary':  ['collection', 'collected', 'overdue', 'arrear', 'repay',
                               'par', 'installment', 'instalment', 'default', 'late'],
    'CollectionMonthly':      ['trend', 'monthly', 'month', 'over time', 'per month',
                               'by month', 'collection', 'collected'],
    'CollectionDaily':        ['daily', 'day', 'today', 'per day', 'date range',
                               'last 7 days', 'this week'],
    'ScheduleMonthly':        ['schedule', 'due', 'expected', 'expected vs',
                               'installment due', 'demand'],
    'AcFisTrialBalanceReportData': ['trial balance', 'balance sheet', 'profit',
                               'loss', 'p&l', 'income', 'expense', 'ledger balance',
                               'financial', 'accounting', 'gl', 'closing balance'],
    'AcLedger':               ['ledger', 'account', 'chart of accounts', 'accounting', 'gl'],
    'MfMemberDeposit':        ['savings', 'saving', 'deposit', 'dps'],
    'MfBadDebtsCollection':   ['bad debt', 'baddebt', 'write off', 'written off', 'recovery'],
    'MfGroup':                ['group'],
    'AdBranch':               ['branch'],
    'HrEmployee':             ['employee', 'officer', 'staff', ' lo ', 'loan officer'],
    'MfMemberBusiness':       ['business', 'sector', 'industry', 'occupation', 'trade'],
    'MfMemberAdditionalInfo': ['additional info', 'extra info'],
    'MfLoanGrantor':          ['guarantor', 'grantor'],
}


def _select_tables(question):
    q = f" {question.lower()} "
    available = set(schema_mod.get_table_names())
    chosen = [t for t in _CORE_TABLES if t in available]
    for table, keywords in _TABLE_KEYWORDS.items():
        if table in available and table not in chosen:
            if any(kw in q for kw in keywords):
                chosen.append(table)
    # Fall back to everything if nothing in the warehouse matched our core list.
    return chosen or list(available)


# Prompt construction
def build_prompt(question):
    tables = _select_tables(question)
    schema_text = schema_mod.get_schema_text(tables)
    return f"""You are an expert data analyst. Generate ONE DuckDB SQL query that
answers the user's question about a microfinance database covering 4 countries.

Rules:
- Output ONLY the SQL query. No explanation, no markdown, no comments.
- Use only the tables and columns shown in the schema.
- It must be a single read-only SELECT statement.

{GLOSSARY}

Database schema:
{schema_text}

Example questions and the correct SQL:
{examples_text()}

-- Question: {question}
"""


#  Call the local Ollama model
def generate_sql(question, timeout=120):
    prompt = build_prompt(question)
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            'model': ASK_AI_MODEL,
            'prompt': prompt,
            'stream': False,
            'keep_alive': OLLAMA_KEEP_ALIVE,
            'options': {
                'temperature': 0,        # deterministic SQL
                'num_predict': 400,
            },
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get('response', '')


#  Guardrail: make the SQL safe to run
_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|'
    r'export|import|truncate|replace|call|set|grant|revoke)\b',
    re.IGNORECASE,
)


def sanitize_sql(raw):
    """Clean model output and reject anything that is not a single SELECT."""
    sql = raw.strip()

    # Strip ```sql ... ``` fences if present.
    fence = re.search(r"```(?:sql)?\s*(.*?)```", sql, re.DOTALL | re.IGNORECASE)
    if fence:
        sql = fence.group(1).strip()

    # Keep only the first statement.
    sql = sql.split(';')[0].strip()
    if not sql:
        raise ValueError("Model returned an empty query.")

    lowered = sql.lower()
    if not (lowered.startswith('select') or lowered.startswith('with')):
        raise ValueError("Only SELECT queries are allowed.")
    if _FORBIDDEN.search(sql):
        raise ValueError("Query contains a disallowed (write/DDL) keyword.")

    # Cap row count if the model did not.
    if not re.search(r'\blimit\b', lowered):
        sql = f"{sql}\nLIMIT {MAX_RESULT_ROWS}"
    return sql


#  Execute on the read-only warehouse
def run_sql(sql):
    if not os.path.exists(WAREHOUSE_PATH):
        raise FileNotFoundError(
            f"Warehouse not found at {WAREHOUSE_PATH}. "
            "Run:  python -m ask_ai.sync_warehouse"
        )
    con = duckdb.connect(WAREHOUSE_PATH, read_only=True)
    try:
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
        return columns, rows
    finally:
        con.close()


#   phrase a one-line natural-language answer
def summarize(question, columns, rows, timeout=60):
    preview = rows[:20]
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            'model': ASK_AI_MODEL,
            'prompt': (
                "Answer the user's question in ONE short sentence using the data.\n"
                f"Question: {question}\n"
                f"Columns: {columns}\n"
                f"Rows: {preview}\n"
                "Answer:"
            ),
            'stream': False,
            'keep_alive': OLLAMA_KEEP_ALIVE,
            'options': {'temperature': 0.2, 'num_predict': 120},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get('response', '').strip()


#  member-analysis vs data question
_MEMBER_CODE = re.compile(r'\bCLN\d+\b', re.IGNORECASE)


_STRONG_HINTS = [
    'analyze member', 'analyse member', 'analyze client', 'analyse client',
    'credit score for', 'member information', 'member info', 'member details',
    'this member', 'about .*member', 'information (about|on|of)', 'profile of',
    'details of', 'give me .*member', 'assess member', 'assess client',
]

_WEAK_HINTS = [
    'can .* get a loan', 'give .* loan', 'loan to ', 'eligible', 'creditworth',
    'assess ', 'condition of ', 'how much loan', 'loan amount for',
    'should we lend', 'risk of ',
]


def _is_strong(question):
    q = question.lower()
    return bool(_MEMBER_CODE.search(question)) or any(re.search(h, q) for h in _STRONG_HINTS)


def _is_weak(question):
    q = question.lower()
    return any(re.search(h, q) for h in _WEAK_HINTS)


def is_member_analysis(question):
    """True if the question could be about assessing a specific member."""
    return _is_strong(question) or _is_weak(question)


def route(question, country=None, with_summary=True):

    strong = _is_strong(question)
    if strong or _is_weak(question):
        from ask_ai.member_analysis import analyze_member
        analysis = analyze_member(question, country=country)
        if analysis.get('success') or strong:
            return analysis
        # weak intent + no member matched → treat as a data question.
    result = ask(question, with_summary=with_summary)
    result['mode'] = 'sql'
    return result


#  Public entry point
def ask(question, with_summary=True):
    """
    Answer a natural-language question.
    Returns: {success, question, sql, columns, rows, row_count, answer?, error?}
    """
    if not question or not question.strip():
        return {'success': False, 'error': 'Empty question.'}

    raw_sql = None
    try:
        raw_sql = generate_sql(question)
        sql = sanitize_sql(raw_sql)
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Ollama unavailable: {e}'}
    except ValueError as e:
        return {'success': False, 'error': str(e), 'sql': raw_sql}

    try:
        columns, rows = run_sql(sql)
    except Exception as e:
        # Surface the SQL so a bad generation is easy to debug / add as an example.
        return {'success': False, 'error': f'SQL execution failed: {e}', 'sql': sql}

    result = {
        'success': True,
        'question': question,
        'sql': sql,
        'columns': columns,
        'rows': rows,
        'row_count': len(rows),
    }

    if with_summary:
        try:
            result['answer'] = summarize(question, columns, rows)
        except requests.exceptions.RequestException:
            result['answer'] = None  # data is still returned even if phrasing fails

    return result
