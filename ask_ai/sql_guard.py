"""
Turn raw model output into a single SQL statement that is safe to run on DW.

The DW login has write and DDL rights, so this is the first of four layers:
guard (here) -> dry-run validation -> rollback-wrapped execution -> row cap.
"""
import re

from ask_ai.config import MAX_RESULT_ROWS, COUNTRY_CODES

_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|create|truncate|merge|exec|execute|'
    r'grant|revoke|deny|backup|restore|shutdown|reconfigure|waitfor|openrowset|'
    r'opendatasource|bulk|xp_\w+|sp_\w+)\b',
    re.IGNORECASE,
)

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# 'string literals' and [bracketed names] may legally contain words like Set or
# Delete; block comments and -- comments may hide a second statement.
_LITERAL = re.compile(r"'(?:[^']|'')*'|\[[^\]]*\]")
_LINE_COMMENT = re.compile(r'--[^\n]*')
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

_SELECT_HEAD = re.compile(r'^\s*select\s+(distinct\s+)?', re.IGNORECASE)
_HAS_TOP = re.compile(r'^\s*select\s+(distinct\s+)?top\s*[\s(]', re.IGNORECASE)


class UnsafeSQL(ValueError):
    """The model produced something we will not send to the warehouse.

    `fixable` marks the cases worth one repair attempt (the model aimed at the
    wrong country). Write/DDL and multi-statement output is never fixable —
    retrying that is pointless, and refusing it is the whole point of the guard.
    """

    def __init__(self, message, fixable=False):
        super().__init__(message)
        self.fixable = fixable


def _blank(match):
    """Blank a span but keep its length, so offsets still line up with the original."""
    return ' ' * len(match.group(0))


def _strip_comments(sql):
    """Comments can hide a second statement, so they never count as code."""
    return _LINE_COMMENT.sub(_blank, _BLOCK_COMMENT.sub(_blank, sql))


def _strip_noise(sql):
    """Comments *and* literal text blanked out. Keyword checks run against this
    so that a legitimate `WHERE Status = 'Deleted'` is not mistaken for a DELETE."""
    return _LITERAL.sub(_blank, _strip_comments(sql))


def sanitize(raw, country=None):
    """Clean model output and reject anything that is not one read-only SELECT.

    Returns the SQL ready to execute. Raises UnsafeSQL otherwise.
    """
    sql = (raw or '').strip()

    fence = _FENCE.search(sql)
    if fence:
        sql = fence.group(1).strip()

    # Some models prefix a stray label even when told not to.
    sql = re.sub(r'^\s*(sql|query)\s*:\s*', '', sql, flags=re.IGNORECASE).strip()

    if not sql:
        raise UnsafeSQL('The model returned an empty query.')

    code = _strip_noise(sql)

    # One statement only. A trailing semicolon is fine; anything after it is not.
    head, _, tail = code.partition(';')
    if tail.strip():
        raise UnsafeSQL('Only a single SQL statement is allowed.')
    if head.strip() != code.strip():
        sql = sql[:len(head)]
        code = head
    sql = sql.strip().rstrip(';').strip()
    code = code.strip().rstrip(';').strip()

    if re.search(r'^\s*go\s*$', code, re.IGNORECASE | re.MULTILINE):
        raise UnsafeSQL('Only a single SQL statement is allowed.')

    lowered = code.lstrip().lower()
    if not (lowered.startswith('select') or lowered.startswith('with')):
        raise UnsafeSQL('Only SELECT queries are allowed.')

    forbidden = _FORBIDDEN.search(code)
    if forbidden:
        raise UnsafeSQL(
            f'Query contains a disallowed keyword: {forbidden.group(0).upper()}.'
        )

    if country:
        if country not in COUNTRY_CODES:
            raise UnsafeSQL(f'Unknown country "{country}".')
        # Reporting on the WRONG country is unambiguous, so it stays fatal.
        # A merely *absent* filter is not — see has_country_filter().
        other = conflicting_country(sql, country)
        if other:
            raise UnsafeSQL(
                f"Query filters on {other} but the question is scoped to {country}.",
                fixable=True,
            )

    return _cap_rows(sql, code)


def _country_patterns(code, country_id):
    """Every way a query can legitimately scope itself to one country."""
    yield rf"CountryCode\s*(?:=|like)\s*N?'{code}'"
    yield rf"CountryCode\s+in\s*\([^)]*'{code}'"
    if country_id is not None:
        yield rf"CountryId\s*=\s*{country_id}\b"
        yield rf"CountryId\s+in\s*\([^)]*\b{country_id}\b"


def _country_id(code):
    """Numeric id for a country code, or None if DW cannot be reached — the
    caller then simply loses the CountryId form, it does not break."""
    try:
        from ask_ai import schema
        return schema.country_ids().get(code)
    except Exception:
        return None


def has_country_filter(sql, country):
    """True when the SQL scopes itself to `country`.

    The country predicate lives inside a string literal, so this reads the
    comment-stripped SQL rather than the literal-stripped `code`. It accepts
    every equivalent form — `= 'KY'`, `= N'KY'`, `IN ('KY')`, `LIKE 'KY'`,
    and `CountryId = 1` — because demanding one exact spelling rejected correct
    queries.
    """
    if not country:
        return True
    text = _strip_comments(sql)
    country_id = _country_id(country)
    return any(re.search(p, text, re.IGNORECASE)
               for p in _country_patterns(country, country_id))


def conflicting_country(sql, country):
    """The code of a different country this SQL explicitly filters on, if any.

    Only an explicit filter counts — a query that scopes itself some other way
    (a branch that exists in one country only) conflicts with nothing.
    """
    text = _strip_comments(sql)
    for other in COUNTRY_CODES:
        if other == country:
            continue
        if any(re.search(p, text, re.IGNORECASE)
               for p in _country_patterns(other, _country_id(other))):
            return other
    return None


def _cap_rows(sql, code):
    """T-SQL has no LIMIT — inject TOP (n) so a runaway query cannot stream a
    million rows back through Flask."""
    if _HAS_TOP.match(code):
        return sql
    if code.lstrip().lower().startswith('with'):
        # TOP belongs on the CTE's final SELECT, which is not reliably locatable
        # by regex. db.run_sql caps the rows it materialises, so this is covered.
        return sql
    match = _SELECT_HEAD.match(sql)
    if not match:
        return sql
    return f'{sql[:match.end()]}TOP ({MAX_RESULT_ROWS}) {sql[match.end():]}'


def strip_limit(sql):
    """Models trained on other dialects reach for LIMIT. Rewrite a trailing
    LIMIT n into TOP (n) rather than failing the whole generation."""
    match = re.search(r'\blimit\s+(\d+)\s*;?\s*$', sql, re.IGNORECASE)
    if not match:
        return sql
    n = int(match.group(1))
    body = sql[:match.start()].rstrip()
    if _HAS_TOP.match(body):
        return body
    head = _SELECT_HEAD.match(body)
    if not head:
        return body
    return f'{body[:head.end()]}TOP ({n}) {body[head.end():]}'
