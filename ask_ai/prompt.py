

import re

from ask_ai import schema as schema_mod
from ask_ai.glossary import GLOSSARY, JOIN_RULES, METRIC_CTES, examples_text

# Only plausibly-needed tables are described
_CORE_TABLES = ['MfMember', 'MfLoan']

_TABLE_KEYWORDS = {
    'MfMember':               ['member', 'client', 'customer', 'borrower', 'people',
                               'user', 'person', 'clients', 'users', 'members',
                               'women', 'woman', 'female', 'men', 'male', 'gender',
                               'age', 'admission', 'joined', 'district'],
    'MfLoan':                 ['loan', 'portfolio', 'principal', 'disburse', 'cycle',
                               'amount', 'outstanding', 'borrower'],
    'MfLoanCollection':       ['collection', 'collected', 'overdue', 'arrear', 'repay',
                               'par', 'installment', 'instalment', 'default', 'late',
                               'daily', 'today', 'recovery'],
    'MfLoanSchedule':         ['schedule', 'due', 'expected', 'demand', 'installment due',
                               'expected vs'],
    'MfLoanProduct':          ['product', 'scheme', 'uml', 'ubl', 'easyloan'],
    'MfLoanApplication':      ['application', 'applied', 'pending approval'],
    'MfLoanPurpose':          ['purpose', 'reason for loan'],
    'MfLoanGrantor':          ['guarantor', 'grantor'],
    'MfMemberBusiness':       ['business', 'sector', 'industry', 'occupation', 'trade'],
    'MfMemberAdditionalInfo': ['additional info', 'extra info'],
    # MfMember has no BranchId — MfGroup is the only bridge to a branch.
    'MfGroup':                ['group', 'groups', 'centre', 'center',
                               'branch', 'branches'],
    'MfTrendReport':          ['trend', 'monthly', 'month', 'over time', 'per month',
                               'by month', 'par', 'ageing', 'aging', 'bucket'],
    'MfPerformanceTracker':   ['performance', 'tracker', 'productivity'],
    'MfPerformanceTrackerData': ['performance', 'tracker', 'productivity', 'officer',
                               'daily disbursement', 'new admission'],
    'MfBadDebtsLoan':         ['bad debt', 'baddebt', 'write off', 'written off', 'npl'],
    'MfBadDebtsCollection':   ['bad debt', 'baddebt', 'recovery', 'recovered'],
    'AcFisTrialBalanceReportData': ['trial balance', 'balance sheet', 'profit', 'loss',
                               'p&l', 'income', 'expense', 'ledger balance',
                               'financial', 'accounting', 'gl', 'closing balance'],
    'AcLedger':               ['ledger', 'account', 'chart of accounts', 'accounting', 'gl'],
    'AcLedgerClassification': ['classification', 'chart of accounts'],
    'AcBusinessDay':          ['business day', 'day open', 'day close'],
    'HrEmployee':             ['employee', 'officer', 'staff', ' lo ', 'loan officer',
                               'salary', 'hr'],
    'HrDesignation':          ['designation', 'role', 'position', 'title'],
    'HrDepartment':           ['department'],
    'AdBranch':               ['branch', 'branches'],
    'AdArea':                 ['area'],
    'AdRegion':               ['region'],
    'AdDivision':             ['division'],
}

_CTE_KEYWORDS = ('collection', 'collected', 'overdue', 'arrear', 'par', 'repay',
                 'trend', 'expected', 'due', 'schedule', 'installment', 'instalment')


def select_tables(question):
    q = f" {question.lower()} "
    available = set(schema_mod.get_table_names())
    chosen = [t for t in _CORE_TABLES if t in available]
    for table, keywords in _TABLE_KEYWORDS.items():
        if table in available and table not in chosen:
            if any(kw in q for kw in keywords):
                chosen.append(table)
    return chosen or list(available)


def _member_scope(member):
    if not member:
        return ''
    member_id, code = member.get('MemberId'), member.get('CountryCode')
    return (f"This question is about ONE member: MemberId {member_id}, MemberCode "
            f"{member.get('MemberCode')}, CountryCode {code}, GroupId {member.get('GroupId')}. "
            f"Identify them with MemberId = {member_id} AND CountryCode = '{code}' "
            "(MemberCode repeats across countries). Answer only what is asked about this member.")


def build_prompt(question, country=None, member=None):
    tables = select_tables(question)
    schema_text = schema_mod.get_schema_text(tables)

    if country:
        scope = (f"Answer for {country} ONLY. Every query must filter "
                 f"CountryCode = '{country}'.")
    else:
        scope = ("No country was pre-selected. If the question itself names a "
                 "country, filter on that one (Uganda=UG, Kenya=KY, Zambia=ZM, "
                 "Tanzania=TZ). If it does not, do not filter by country — add "
                 "GROUP BY CountryCode when a per-country breakdown helps. "
                 "Never write CountryCode IN ('UG','KY','ZM','TZ'); just omit "
                 "the filter.")

    blocks = [
        "You are an expert data analyst. Generate ONE Microsoft SQL Server "
        "(T-SQL) query that answers the user's question about a microfinance "
        "data warehouse covering 4 countries.",
        "Rules:\n"
        "- Output ONLY the SQL query. No explanation, no markdown, no comments.\n"
        "- Use only the tables and columns shown in the schema.\n"
        "- It must be a single read-only SELECT statement.\n"
        "- T-SQL only: TOP (n), never LIMIT.\n"
        f"- {scope}",
        GLOSSARY,
    ]
    if member:
        blocks.insert(2, _member_scope(member))
    if any(kw in question.lower() for kw in _CTE_KEYWORDS):
        blocks.append(METRIC_CTES)
    blocks.append(f"Database schema:\n{schema_text}")
    blocks.append(f"Example questions and the correct SQL:\n{examples_text(tables)}")
    blocks.append(f"-- Question: {question}")
    return "\n\n".join(blocks)


_BAD_COLUMN = re.compile(r"Invalid column name '([^']+)'", re.IGNORECASE)


def _column_hint(error, tables):

    match = _BAD_COLUMN.search(error or '')
    if not match:
        return ''
    column = match.group(1)
    owners = schema_mod.tables_with_column(column)
    if not owners:
        return f"\nNo table in this schema has a column called {column}.\n"
    relevant = [t for t in owners if t in set(tables)] or owners
    return (f"\n{column} does not exist on the table you used. "
            f"It exists on: {', '.join(relevant)}.\n"
            "Join to one of those instead of inventing the column.\n")


def build_repair_prompt(question, sql, error, country=None, member=None):

    tables = select_tables(question)
    return (
        "The following Microsoft SQL Server query failed. Fix it.\n\n"
        f"Question: {question}\n\n"
        + (f"{_member_scope(member)}\n\n" if member else "")
        + f"Failed SQL:\n{sql}\n\n"
        f"Failed SQL:\n{sql}\n\n"
        f"SQL Server error:\n{error}\n"
        f"{_column_hint(error, tables)}\n"
        f"Database schema:\n{schema_mod.get_schema_text(tables)}\n\n"
        f"{JOIN_RULES}\n\n"
        "Other common causes: LIMIT instead of TOP (n), a join missing "
        "'AND a.CountryId = b.CountryId', or a column referenced without being "
        "in GROUP BY.\n"
        + (f"The answer must stay filtered to CountryCode = '{country}'.\n"
           if country else "")
        + "\nOutput ONLY the corrected SQL query. No explanation, no markdown."
    )
