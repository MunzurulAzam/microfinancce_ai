
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from ask_ai import db                            # noqa: E402  (must follow load_dotenv)
from ask_ai.engine import is_member_analysis     # noqa: E402
from ask_ai.glossary import EXAMPLES             # noqa: E402
from ask_ai.sql_guard import (                   # noqa: E402
    has_country_filter, sanitize, scope_to_country, UnsafeSQL,
)

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
    """Correct SQL must not be rejected for spelling the country filter differently."""
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


SCOPE_CASES = [
    ("SELECT COUNT(*) FROM MfMember m JOIN MfLoan l ON l.MemberId = m.MemberId "
     "WHERE m.CountryCode = 'KY'", ['MfMember', 'MfLoan']),
    ("SELECT COUNT(*) FROM MfLoan WHERE CountryCode = 'KY' OR TotalOutstanding > 1000",
     ['MfLoan']),
    ("SELECT SUM(CASE WHEN CountryCode = 'KY' THEN 1 ELSE 0 END) AS n FROM MfMember",
     ['MfMember']),
    ("SELECT SUM(l.TotalOutstanding) FROM MfLoan l WHERE l.MemberId IN "
     "(SELECT MemberId FROM MfMember)", ['MfLoan', 'MfMember']),
    ("WITH ky AS (SELECT MemberId FROM MfMember) SELECT COUNT(*) FROM ky", ['MfMember']),
    ("SELECT COUNT(*) FROM MfMember", ['MfMember']),
    ("SELECT COUNT(*) FROM dbo.MfMember AS m", ['MfMember']),
    ("SELECT COUNT(*) FROM [MfMember] m", ['MfMember']),
    ("SELECT COUNT(*) FROM MfMember m, MfLoan l WHERE l.MemberId = m.MemberId",
     ['MfMember', 'MfLoan']),
    ("SELECT b.BranchName FROM MfMember m JOIN MfGroup g ON g.GroupId = m.GroupId "
     "JOIN AdBranch b ON b.BranchId = g.BranchId", ['MfMember', 'MfGroup', 'AdBranch']),
    ("SELECT COUNT(*) FROM MfMember WHERE FirstName = 'FROM MfLoan x'", ['MfMember']),
    ("SELECT COUNT(*) FROM DW.dbo.MfMember m", ['MfMember']),
    ("SELECT COUNT(*) FROM [dbo].[MfMember] m", ['MfMember']),
    ("SELECT COUNT(*) FROM MfMember m LEFT OUTER JOIN MfLoan l "
     "ON l.MemberId = m.MemberId", ['MfMember', 'MfLoan']),
    ("SELECT COUNT(*) FROM MfMember UNION ALL SELECT COUNT(*) FROM MfLoan",
     ['MfMember', 'MfLoan']),
    ("WITH a AS (SELECT * FROM MfMember), b AS (SELECT * FROM MfLoan) "
     "SELECT COUNT(*) FROM a JOIN b ON b.MemberId = a.MemberId", ['MfMember', 'MfLoan']),
    ("SELECT (SELECT COUNT(*) FROM MfLoan) AS n FROM MfMember", ['MfMember', 'MfLoan']),
    ("SELECT * FROM MfLoan l CROSS APPLY (SELECT TOP 1 * FROM MfLoanCollection c "
     "WHERE c.LoanId = l.LoanId) x", ['MfLoan', 'MfLoanCollection']),
    ("SELECT COUNT(*) FROM MfMember /* FROM MfLoan */ m", ['MfMember']),
]

SCOPE_REJECTS = [
    "SELECT COUNT(*) FROM SomeOtherTable t",
    "SELECT COUNT(*) FROM MfMember m JOIN sys.objects o ON o.name = m.FirstName",
    "WITH MfMember AS (SELECT * FROM MfMember) SELECT COUNT(*) FROM MfMember",
]


def check_country_scope():
    """Every base table must come out wrapped in a country filter, or be rejected."""
    failures = []
    for sql, tables in SCOPE_CASES:
        try:
            scoped = scope_to_country(sql, 'KY')
        except UnsafeSQL as e:
            failures.append(sql)
            print(f"FAIL scope    wrongly rejected: {sql}\n          {e}")
            continue
        for table in tables:
            if f"(SELECT * FROM {table} WHERE CountryCode = 'KY')" not in scoped:
                failures.append(sql)
                print(f"FAIL scope    {table} left unscoped: {sql}\n          {scoped}")

    for sql in SCOPE_REJECTS:
        try:
            scope_to_country(sql, 'KY')
            failures.append(sql)
            print(f"FAIL scope    should have been rejected: {sql}")
        except UnsafeSQL:
            pass

    total = len(SCOPE_CASES) + len(SCOPE_REJECTS)
    print(f"{total - len(failures)}/{total} country-scope cases correct")
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
        print(f"{len(empty)} returned no rows: {', '.join(empty)}")

    routing_failures = check_routing()
    country_failures = check_country_guard()
    scope_failures = check_country_scope()
    return 1 if (failures or routing_failures or country_failures
                 or scope_failures) else 0


if __name__ == '__main__':
    sys.exit(main())
