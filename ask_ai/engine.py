

import re

from ask_ai import db, llm
from ask_ai.cache import TTLCache
from ask_ai.config import RESULT_CACHE_TTL
from ask_ai.prompt import build_prompt, build_repair_prompt
from ask_ai.sql_guard import sanitize, strip_limit, UnsafeSQL

_results = TTLCache(RESULT_CACHE_TTL, max_entries=128)


def _cache_key(question, country, with_summary):
    return (' '.join(question.lower().split()), country, with_summary)


# A member code proves one person; the phrase "... member ..." does not.
_MEMBER_CODE = re.compile(r'\bCLN\d+\b', re.IGNORECASE)
_MEMBER_ID = re.compile(r'^\s*\d{3,}\s*$')

# Aggregate wording means a set of people, so it vetoes every phrase hint below.
_AGGREGATE = re.compile(
    r'\b(total|totals|list|all|how many|count|counts|each|per|every|top|'
    r'average|avg|sum|names|breakdown|compare|trend|branch|branches|group|'
    r'groups|report|highest|lowest|most|least)\b',
    re.IGNORECASE,
)

_STRONG_HINTS = [
    'analyze member', 'analyse member', 'analyze client', 'analyse client',
    'credit score for', 'member information', 'member info', 'member details',
    'this member', 'profile of', 'assess member', 'assess client',
]

_WEAK_HINTS = [
    'can .* get a loan', 'give .* loan', 'loan to ', 'eligible', 'creditworth',
    'assess ', 'condition of ', 'how much loan', 'loan amount for',
    'should we lend', 'risk of ',
]


def _names_one_person(question):
    """A member code outranks aggregate wording — "all loans of CLN0189567" is still one person."""
    return bool(_MEMBER_CODE.search(question)) or bool(_MEMBER_ID.match(question))


def _is_strong(question):
    if _names_one_person(question):
        return True
    if _AGGREGATE.search(question):
        return False
    q = question.lower()
    return any(re.search(h, q) for h in _STRONG_HINTS)


def _is_weak(question):
    if _AGGREGATE.search(question):
        return False
    q = question.lower()
    return any(re.search(h, q) for h in _WEAK_HINTS)


def is_member_analysis(question):
    """True if the question is about assessing one specific member."""
    return _is_strong(question) or _is_weak(question)


def route(question, country=None, with_summary=True):
    from reports.service import REPORT_NAMES, parse_question, create_report, ReportError, enrich_period_error
    if REPORT_NAMES.search(question):
        try:
            return create_report(parse_question(question), country, with_summary)
        except ReportError as error:
            return dict(enrich_period_error(error, country).payload(), bad_request=error.status < 500)
    strong = _is_strong(question)
    if strong or _is_weak(question):
        from ask_ai.member_analysis import analyze_member
        analysis = analyze_member(question, country=country)
        if analysis.get('success') or strong:
            return analysis
    result = ask(question, country=country, with_summary=with_summary)
    result['mode'] = 'sql'
    return result


def _generate_sql(question, country):
    """Ask the model for SQL, then make it safe."""
    try:
        prompt = build_prompt(question, country)
    except db.QueryError as e:
        return None, None, {'error': 'Warehouse unavailable. Please retry later.', 'code': 'warehouse_unavailable', 'http_status': 503, 'retryable': True}, False

    result = llm.generate(prompt)
    if not result['success']:
        return None, None, result, False

    raw = result['text']
    try:
        return sanitize(strip_limit(raw or ''), country=country), raw, None, True
    except UnsafeSQL as e:
        if not getattr(e, 'fixable', False):
            return None, raw, str(e), True
        fixed, fix_error = _repair_sql(question, raw, str(e), country)
        if fixed:
            return fixed, raw, None, True
        return None, raw, fix_error or str(e), True


def _repair_sql(question, sql, error, country):
    """One retry, handed the failed SQL and the server's own complaint."""
    result = llm.generate(build_repair_prompt(question, sql, error, country))
    if not result['success']:
        return None, result
    try:
        return sanitize(strip_limit(result['text'] or ''), country=country), None
    except UnsafeSQL as e:
        return None, str(e)


def ask(question, country=None, with_summary=True):
    """Answer a natural-language question against DW."""
    if not question or not question.strip():
        return {'success': False, 'error': 'Empty question.', 'bad_request': True}

    key = _cache_key(question, country, with_summary)
    cached = _results.get(key)
    if cached is not None:
        return dict(cached, cached=True)

    sql, raw, error, caller_fault = _generate_sql(question, country)
    if not sql:
        if isinstance(error, dict):
            return {k: v for k, v in dict(error, success=False, sql=raw, bad_request=caller_fault).items() if k != 'text'}
        return {'success': False, 'error': error, 'sql': raw, 'bad_request': caller_fault}

    ok, validation_error, _ = db.validate_sql(sql)
    if not ok:
        repaired, repair_error = _repair_sql(question, sql, validation_error, country)
        if repaired:
            ok, second_error, _ = db.validate_sql(repaired)
            if ok:
                sql = repaired
            else:
                return _invalid(question, sql, validation_error, repaired, second_error)
        else:
            return _invalid(question, sql, validation_error, None, repair_error)

    try:
        columns, rows, truncated = db.run_sql(sql)
    except db.QueryError as e:
        return {'success': False, 'error': 'Warehouse query failed. Please retry later.', 'code': 'warehouse_query_failed', 'http_status': 503, 'retryable': True, 'sql': sql}

    result = {
        'success': True,
        'question': question,
        'country': country,
        'sql': sql,
        'columns': columns,
        'rows': rows,
        'row_count': len(rows),
        'truncated': truncated,
    }
    if country:
        result['country_enforced'] = True

    if with_summary:
        result['answer'] = llm.summarize(question, columns, rows)

    _results.set(key, result)
    return result


def _invalid(question, sql, error, repaired, repair_error):
    """Return both failed attempts so a bad generation is easy to turn into a new example."""
    if isinstance(repair_error, dict):
        return dict(repair_error, success=False, question=question, sql=sql)
    return {
        'success': False,
        'question': question,
        'error': f'Could not build valid SQL for that question. {error}',
        'sql': sql,
        'attempted_fix': repaired,
        'fix_error': repair_error,
        'bad_request': True,
    }
