

from ask_ai import engine, schema as schema_mod
from ask_ai.config import DIFY_TABLE_ROWS
from ask_ai.glossary import GLOSSARY, examples_text
from ask_ai.prompt import select_tables

_ALL_COUNTRIES = 'all 4 countries (UG/KY/ZM/TZ)'

# Live answers are computed for this exact question, so they are never a partial match.
_LIVE_SCORE = 1.0

_RULES_SCORE = 1.0
_EXAMPLES_SCORE = 0.95
_TABLE_TOP_SCORE = 0.9
_TABLE_STEP = 0.05
_MIN_SCORE = 0.5


def _record(content, score, title, metadata):
    return {'content': content, 'score': score, 'title': title, 'metadata': metadata}


def _cell(value):
    """A newline or a pipe inside a value would break the markdown table."""
    if value is None:
        return ''
    return str(value).replace('|', r'\|').replace('\n', ' ')


def _markdown_table(columns, rows):
    header = f"| {' | '.join(columns)} |"
    divider = f"| {' | '.join('---' for _ in columns)} |"
    body = [f"| {' | '.join(_cell(row.get(c)) for c in columns)} |" for row in rows]
    return '\n'.join([header, divider] + body)


def live_records(query, country=None):
    """Run the question through the engine. Returns (records, error)."""
    result = engine.route(query, country=country, with_summary=True)
    if not result.get('success'):
        return [], result.get('error')
    if result.get('mode') == 'report':
        report = result['report']
        return [_record(result['answer'], _LIVE_SCORE, report['title'], {'mode': 'report', 'report_id': report['report_id'], 'period': report['period']})], None
    if result.get('mode') == 'member_analysis':
        return [_member_record(query, result, country)], None
    return [_sql_record(query, result, country)], None


def _sql_record(query, result, country):
    columns = result.get('columns') or []
    rows = result.get('rows') or []
    shown = rows[:DIFY_TABLE_ROWS]
    truncated = bool(result.get('truncated')) or len(shown) < len(rows)

    lines = [
        f"Question: {query}",
        f"Answer: {result.get('answer') or '(read the data below)'}",
        f"Country scope: {country or _ALL_COUNTRIES}",
        f"Rows: {result.get('row_count', len(rows))}" + (' (truncated)' if truncated else ''),
    ]
    if columns and shown:
        lines += ['', _markdown_table(columns, shown)]
    lines += ['', f"SQL used:\n{result.get('sql', '')}"]

    return _record(
        '\n'.join(lines),
        _LIVE_SCORE,
        query.strip()[:120],
        {
            'source': 'DW warehouse (live SQL)',
            'mode': 'sql',
            'sql': result.get('sql'),
            'row_count': result.get('row_count', len(rows)),
            'country': country or 'ALL',
            'truncated': truncated,
        },
    )


def _member_record(query, result, country):
    member = result.get('member') or {}
    lines = [
        f"Question: {query}",
        f"Member: {member.get('name')} ({member.get('code')}) — {member.get('country')}",
        f"Group: {member.get('group')} | Branch: {member.get('branch')} | "
        f"Loan officer: {member.get('loan_officer')}",
        f"Credit score: {result.get('score')}% — {result.get('classification')} "
        f"(risk level {result.get('risk_level')})",
        f"Decision: {result.get('decision')}",
        f"Condition: {result.get('condition_summary')}",
        f"Recommended loan amount: {result.get('recommended_loan_amount')} "
        f"({result.get('amount_reasoning')})",
    ]
    suggestions = result.get('suggestions') or []
    if suggestions:
        lines += ['Suggestions:'] + [f"- {s}" for s in suggestions]
    if result.get('analysis'):
        lines.append(f"Assessment:\n{result['analysis']}")
    if result.get('match_note'):
        lines.append(result['match_note'])

    return _record(
        '\n'.join(lines),
        _LIVE_SCORE,
        f"Member assessment — {member.get('code') or query.strip()[:80]}",
        {
            'source': 'DW warehouse (member analysis)',
            'mode': 'member_analysis',
            'member_code': member.get('code'),
            'country': member.get('country') or country or 'ALL',
            'score': result.get('score'),
            'decision': result.get('decision'),
        },
    )


def schema_records(query):
    """Structural knowledge: business rules, verified examples, and the relevant DDL.

    Ranking is the keyword routing prompt.py already uses, not embedding similarity.
    """
    tables = select_tables(query)
    records = [
        _record(GLOSSARY, _RULES_SCORE, 'DW warehouse business rules',
                {'source': 'DW schema', 'kind': 'rules', 'table': None}),
        _record(examples_text(tables), _EXAMPLES_SCORE,
                'Verified example questions and their SQL',
                {'source': 'DW schema', 'kind': 'examples', 'table': None}),
    ]
    for position, table in enumerate(tables):
        ddl = schema_mod.get_schema_text([table])
        if not ddl:
            continue
        records.append(_record(
            ddl,
            max(_MIN_SCORE, round(_TABLE_TOP_SCORE - position * _TABLE_STEP, 2)),
            f'Table {table}',
            {'source': 'DW schema', 'kind': 'table', 'table': table},
        ))
    return records
