"""Turn raw model output into a single SQL statement that is safe to run on DW."""
import re

from ask_ai.config import MAX_RESULT_ROWS, COUNTRY_CODES, TABLE_ALLOWLIST

_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|create|truncate|merge|exec|execute|'
    r'grant|revoke|deny|backup|restore|shutdown|reconfigure|waitfor|openrowset|'
    r'opendatasource|bulk|xp_\w+|sp_\w+)\b',
    re.IGNORECASE,
)

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# Literals and [bracketed names] may contain Set/Delete; comments may hide a second statement.
_LITERAL = re.compile(r"'(?:[^']|'')*'|\[[^\]]*\]")
_STRING = re.compile(r"'(?:[^']|'')*'")
_LINE_COMMENT = re.compile(r'--[^\n]*')
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)

_SELECT_HEAD = re.compile(r'^\s*select\s+(distinct\s+)?', re.IGNORECASE)
_HAS_TOP = re.compile(r'^\s*select\s+(distinct\s+)?top\s*[\s(]', re.IGNORECASE)

_ALLOWED_TABLES = {t.lower(): t for t in TABLE_ALLOWLIST}
_SOURCE_KEYWORD = re.compile(r'\b(from|join|apply)\b', re.IGNORECASE)
_TABLE_REF = re.compile(
    r'\s*(?P<prefix>(?:(?:\w+|\[[^\]]+\])\s*\.\s*){1,2})?'
    r'(?:\[(?P<quoted>[^\]]+)\]|(?P<plain>\w+))',
    re.IGNORECASE,
)
_CTE_NAME = re.compile(r'(?:\bwith\b|,)\s*(\w+)\s+as\s*\(', re.IGNORECASE)
_FROM_LIST_COMMA = re.compile(r'\s*(?:as\s+)?(?:\w+)?\s*,', re.IGNORECASE)
_FOLLOWING_WORD = re.compile(r'\s+(?:as\s+)?(\w+)', re.IGNORECASE)
_NOT_AN_ALIAS = frozenset((
    'on', 'where', 'group', 'order', 'having', 'join', 'inner', 'left', 'right',
    'full', 'cross', 'outer', 'union', 'apply', 'and', 'or', 'except', 'intersect',
    'for', 'option', 'pivot', 'unpivot',
))
_SCOPE_PREFIX = '(SELECT * FROM '


class UnsafeSQL(ValueError):
    """The model produced something we will not send to the warehouse."""

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
    """Comments *and* literal text blanked out."""
    return _LITERAL.sub(_blank, _strip_comments(sql))


def _strip_strings(sql):
    """Like _strip_noise but keeps [bracketed names], which can be table references."""
    return _STRING.sub(_blank, _strip_comments(sql))


def sanitize(raw, country=None):
    """Clean model output and reject anything that is not one read-only SELECT."""
    sql = (raw or '').strip()

    fence = _FENCE.search(sql)
    if fence:
        sql = fence.group(1).strip()

    sql = re.sub(r'^\s*(sql|query)\s*:\s*', '', sql, flags=re.IGNORECASE).strip()

    if not sql:
        raise UnsafeSQL('The model returned an empty query.')

    code = _strip_noise(sql)

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

    if not country:
        return _cap_rows(sql, code)

    if country not in COUNTRY_CODES:
        raise UnsafeSQL(f'Unknown country "{country}".')

    other = conflicting_country(sql, country)
    if other:
        raise UnsafeSQL(
            f"Query filters on {other} but the question is scoped to {country}.",
            fixable=True,
        )

    return scope_to_country(_cap_rows(sql, code), country)


def _country_patterns(code, country_id):
    """Every way a query can legitimately scope itself to one country."""
    yield rf"CountryCode\s*(?:=|like)\s*N?'{code}'"
    yield rf"CountryCode\s+in\s*\([^)]*'{code}'"
    if country_id is not None:
        yield rf"CountryId\s*=\s*{country_id}\b"
        yield rf"CountryId\s+in\s*\([^)]*\b{country_id}\b"


def _country_id(code):
    """Numeric id for a country code, or None if DW is unreachable — callers degrade, not break."""
    try:
        from ask_ai import schema
        return schema.country_ids().get(code)
    except Exception:
        return None


def has_country_filter(sql, country):
    """True when the SQL scopes itself to `country`."""
    if not country:
        return True
    text = _strip_comments(sql)
    country_id = _country_id(country)
    return any(re.search(p, text, re.IGNORECASE)
               for p in _country_patterns(country, country_id))


def conflicting_country(sql, country):
    """The code of a different country this SQL explicitly filters on, if any."""
    text = _strip_comments(sql)
    for other in COUNTRY_CODES:
        if other == country:
            continue
        if any(re.search(p, text, re.IGNORECASE)
               for p in _country_patterns(other, _country_id(other))):
            return other
    return None


def _cte_names(code):
    return {m.group(1).lower() for m in _CTE_NAME.finditer(code)}


def _table_refs(code, ctes):
    refs, seen = [], set()
    for keyword in _SOURCE_KEYWORD.finditer(code):
        pos = keyword.end()
        in_from = keyword.group(1).lower() == 'from'
        while True:
            match = _TABLE_REF.match(code, pos)
            if not match:
                break
            name = match.group('quoted') or match.group('plain')
            if not name or name.lower() in ('select', 'lateral'):
                break
            if match.group('prefix'):
                start = match.start('prefix')
            elif match.group('quoted'):
                start = match.start('quoted') - 1
            else:
                start = match.start('plain')
            if name.lower() not in ctes and start not in seen:
                seen.add(start)
                refs.append((start, match.end(), name))
            following = _FROM_LIST_COMMA.match(code, match.end())
            if in_from and following:
                pos = following.end()
                continue
            break
    return refs


def _is_aliased(code, end):
    following = _FOLLOWING_WORD.match(code, end)
    return bool(following) and following.group(1).lower() not in _NOT_AN_ALIAS


def scope_to_country(sql, country):
    """Restrict every base table to `country` so no join can reach another one."""
    code = _strip_strings(sql)
    ctes = _cte_names(code)

    shadowed = sorted(_ALLOWED_TABLES[n] for n in ctes if n in _ALLOWED_TABLES)
    if shadowed:
        raise UnsafeSQL(
            f"A CTE may not reuse a table name: {', '.join(shadowed)}.",
            fixable=True,
        )

    refs = _table_refs(code, ctes)
    unknown = sorted({name for _, _, name in refs
                      if name.lower() not in _ALLOWED_TABLES})
    if unknown:
        raise UnsafeSQL(
            f"Query uses a table that is not available: {', '.join(unknown)}.",
            fixable=True,
        )

    scoped = sql
    for start, end, name in sorted(refs, reverse=True):
        table = _ALLOWED_TABLES[name.lower()]
        alias = '' if _is_aliased(code, end) else f' {table}'
        scoped = (f"{scoped[:start]}{_SCOPE_PREFIX}{table} "
                  f"WHERE CountryCode = '{country}'){alias}{scoped[end:]}")

    check = _strip_strings(scoped)
    for start, _, name in _table_refs(check, _cte_names(check)):
        if name.lower() in _ALLOWED_TABLES and not check[:start].endswith(_SCOPE_PREFIX):
            raise UnsafeSQL(
                f"Could not scope every reference to {name} to {country}.",
                fixable=True,
            )
    return scoped


def _cap_rows(sql, code):
    """T-SQL has no LIMIT — inject TOP (n) so a runaway query cannot stream a million rows."""
    if _HAS_TOP.match(code):
        return sql
    if code.lstrip().lower().startswith('with'):
        # TOP on a CTE is not regex-locatable — db.run_sql caps the rows instead.
        return sql
    match = _SELECT_HEAD.match(sql)
    if not match:
        return sql
    return f'{sql[:match.end()]}TOP ({MAX_RESULT_ROWS}) {sql[match.end():]}'


def strip_limit(sql):
    """Models trained on other dialects reach for LIMIT."""
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
