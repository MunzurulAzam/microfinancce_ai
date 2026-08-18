"""
Self-check for ask_ai. Two things, neither of which needs the LLM:

  1. every few-shot example in glossary.py still executes against DW — an
     example that does not run is a prompt actively teaching the model to be
     wrong, so this gates any change to EXAMPLES;
  2. questions route to the right pipeline — aggregate questions must reach
     text-to-SQL, not single-member credit analysis;
  3. the country guard recognises every correct way to scope a query, and still
     blocks one aimed at a different country.

    python -m ask_ai.check_examples
"""
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from ask_ai import db                            # noqa: E402  (must follow load_dotenv)
from ask_ai.engine import is_member_analysis     # noqa: E402
from ask_ai.glossary import EXAMPLES             # noqa: E402
from ask_ai.sql_guard import (                   # noqa: E402
    has_country_filter, sanitize, UnsafeSQL,
)

# True = single-member credit analysis, False = text-to-SQL.
ROUTING_CASES = [
    ('give me Nyangusu this branch total member name', False),
    ('give me all member list', False),
    ('how many clients in each branch', False),
    ('total members in Nyangusu branch', False),
    ('which branch has the most members', False),
    ('list all users in Nyangusu branch', False),
    ('analyze member CLN0189567', True),
    ('can CLN0049681 get a loan?', True),
    ('all loans of CLN0189567', True),
    ('analyze client Jesca Acam', True),
]


# (sql, is_scoped_to_KY). All of these are correct Kenya SQL except the last
# two, which carry no country predicate at all.
COUNTRY_CASES = [
    ("SELECT COUNT(*) FROM MfMember WHERE CountryCode = 'KY'", True),
    ("SELECT COUNT(*) FROM MfMember m WHERE m.CountryCode = 'KY'", True),
    ("SELECT COUNT(*) FROM MfMember WHERE CountryCode = N'KY'", True),
    ("SELECT COUNT(*) FROM MfMember WHERE CountryCode IN ('KY')", True),
    ("SELECT COUNT(*) FROM MfMember WHERE CountryCode LIKE 'KY'", True),
    ("SELECT COUNT(*) FROM MfMember WHERE CountryId = 1", True),
    ("SELECT COUNT(*) FROM AdBranch b WHERE b.BranchName = 'Nyangusu'", False),
    ("SELECT COUNT(*) FROM MfMember", False),
]


def check_country_guard():
    """Correct Kenya SQL must never be rejected just for spelling the filter
    differently — that is what broke "give me Nyangusu this branch total member
    name". A query aimed at another country must still be refused."""
    failures = []
    for sql, scoped in COUNTRY_CASES:
        try:
            sanitize(sql, country='KY')
        except UnsafeSQL as e:
            failures.append(sql)
            print(f"FAIL country  wrongly rejected: {sql}\n          {e}")
            continue
        if has_country_filter(sql, 'KY') != scoped:
            failures.append(sql)
            print(f"FAIL country  has_country_filter should be {scoped}: {sql}")

    # Aimed at another country: must be refused, and must say which one. The
    # IN (...) case matters too — it would quietly widen a KY answer to ZM.
    for sql, other in [
        ("SELECT COUNT(*) FROM MfMember WHERE CountryCode = 'UG'", 'UG'),
        ("SELECT COUNT(*) FROM MfMember WHERE CountryId = 3", 'UG'),
        ("SELECT COUNT(*) FROM MfMember WHERE CountryCode IN ('KY','ZM')", 'ZM'),
    ]:
        try:
            sanitize(sql, country='KY')
            failures.append(sql)
            print(f"FAIL country  should have been blocked for KY: {sql}")
        except UnsafeSQL as e:
            if other not in str(e):
                failures.append(sql)
                print(f"FAIL country  message should name {other}, got: {e}")

    total = len(COUNTRY_CASES) + 3
    print(f"{total - len(failures)}/{total} country-guard cases correct")
    return failures


def check_routing():
    """Aggregate wording must never be mistaken for one person."""
    failures = []
    for question, expect_member in ROUTING_CASES:
        got = is_member_analysis(question)
        if got != expect_member:
            failures.append(question)
            want = 'member analysis' if expect_member else 'text-to-SQL'
            print(f"FAIL routing  {question}\n          expected {want}")
    print(f"{len(ROUTING_CASES) - len(failures)}/{len(ROUTING_CASES)} routing cases correct")
    return failures


def main():
    failures = []
    empty = []

    for question, sql in EXAMPLES:
        statement = sanitize(sql)

        ok, error, _ = db.validate_sql(statement)
        if not ok:
            failures.append((question, error))
            print(f"FAIL      {question}\n          {error}")
            continue

        started = time.time()
        try:
            _, rows, _ = db.run_sql(statement)
        except db.QueryError as e:
            failures.append((question, str(e)))
            print(f"FAIL(run) {question}\n          {e}")
            continue

        elapsed = time.time() - started
        if not rows:
            empty.append(question)
            print(f"EMPTY  {elapsed:6.2f}s        {question}")
        else:
            print(f"ok     {elapsed:6.2f}s  {len(rows):>4} rows  {question}")

    print(f"\n{len(EXAMPLES) - len(failures)}/{len(EXAMPLES)} examples valid")
    if empty:
        # Not fatal — but an example returning nothing teaches nothing.
        print(f"{len(empty)} returned no rows: {', '.join(empty)}")

    routing_failures = check_routing()
    country_failures = check_country_guard()
    return 1 if (failures or routing_failures or country_failures) else 0


if __name__ == '__main__':
    sys.exit(main())
