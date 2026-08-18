

import os
import re
from datetime import date, datetime

from credit_scoring.scoring import calculate_credit_score
from ask_ai import db, llm

# Fallback base loan amount for a first-time borrower — no prior loan to scale from.
FIRST_CYCLE_BASE = float(os.environ.get('ASK_AI_FIRST_CYCLE_BASE', 0))

ANALYSIS_MODEL = os.environ.get('ASK_AI_ANALYSIS_MODEL') or None


# small query helpers — all SQL here is hand-written and parameterized
def _rows(sql, params=()):
    try:
        return db.query(sql, tuple(params))
    except db.QueryError as e:
        # An empty result silently deflates the credit score, so make it visible.
        print(f"[ask_ai.member_analysis] query failed: {e}")
        return []


def _one(sql, params=()):
    rows = _rows(sql, params)
    return rows[0] if rows else None


# pull the member reference code / id / name out of a full question
_STOPWORDS = re.compile(
    r'(?i)\b(how much|loan amount|analyze|analyse|member|members|client|customer|can|could|'
    r'give|given|gives|get|gets|getting|a|an|the|to|for|of|is|are|eligible|eligibility|'
    r'creditworthy|creditworthiness|credit|score|scoring|assess|assessment|condition|'
    r'should|we|lend|lending|risk|profile|please|tell|me|about|his|her|their|much|how|'
    r'and|analysis|report|status|information|info|details|detail|this|that|these|those|'
    r'system|in|on|show|find|what|who|whose|does|do|has|have|had)\b')


def extract_member_ref(question):
    """Extract the member identifier (CLN code, numeric id, or name) from a question."""
    m = re.search(r'\bCLN\d+\b', question, re.IGNORECASE)
    if m:
        return m.group(0)
    m = re.search(r'\b\d{3,}\b', question)          # a member id (3+ digits)
    if m:
        return m.group(0)
    cleaned = _STOPWORDS.sub(' ', question)
    cleaned = re.sub(r'[^\w\s]', ' ', cleaned)      # drop punctuation
    return ' '.join(cleaned.split()).strip()


#  resolve member
# MemberId and MemberCode are only unique WITHIN a country — 113k+ codes are
# reused across the four countries — so a lookup without a country filter can
# return several people. Rank the live, most recent record first rather than
# letting the server's row order decide which person gets assessed.
_BEST_FIRST = ("ORDER BY CASE WHEN MemberStatus = 'Active' THEN 0 "
               "WHEN MemberStatus = 'Inactive' THEN 1 ELSE 2 END, "
               "AdmissionDate DESC")


def resolve_member(query, country=None):
    """Find matching members in DW. Returns a list, best first."""
    q = (query or '').strip()
    if not q:
        return []

    where_country = " AND CountryCode = %s" if country else ""
    cp = [country.upper()] if country else []

    if q.isdigit():
        return _rows(
            f"SELECT * FROM MfMember WHERE MemberId = %s{where_country} {_BEST_FIRST}",
            [int(q)] + cp)

    if q.upper().startswith('CLN'):
        return _rows(
            f"SELECT * FROM MfMember WHERE MemberCode = %s{where_country} {_BEST_FIRST}",
            [q] + cp)

    # Name search — every token must appear somewhere in "FirstName LastName".
    parts = [p for p in q.split() if len(p) > 1]
    if parts:
        conds = " AND ".join(["(FirstName + ' ' + LastName) LIKE %s"] * len(parts))
        return _rows(
            f"SELECT TOP (10) * FROM MfMember WHERE {conds}{where_country} {_BEST_FIRST}",
            [f'%{p}%' for p in parts] + cp)

    return _rows(
        f"SELECT TOP (10) * FROM MfMember WHERE (FirstName LIKE %s OR LastName LIKE %s "
        f"OR MemberCode LIKE %s){where_country} {_BEST_FIRST}",
        [f'%{q}%', f'%{q}%', f'%{q}%'] + cp)


def suggest_members(query, country=None, limit=5):
    """Loose 'did you mean' suggestions when an exact resolve fails."""
    ref = extract_member_ref(query)
    tokens = [p for p in ref.split() if len(p) > 1]
    if not tokens:
        return []
    where_country = " AND CountryCode = %s" if country else ""
    cp = [country.upper()] if country else []
    # Match on ANY token (loose).
    ors = " OR ".join(["(FirstName + ' ' + LastName) LIKE %s"] * len(tokens))
    rows = _rows(
        f"SELECT TOP (%s) FirstName, LastName, MemberCode, CountryCode FROM MfMember "
        f"WHERE ({ors}){where_country}",
        [limit] + [f'%{t}%' for t in tokens] + cp)
    return [f"{r['FirstName']} {r['LastName']} ({r['MemberCode']}, {r['CountryCode']})".strip()
            for r in rows]


#  build the scoring `data` dict from DW
def _age(dob):
    if not dob:
        return None
    if isinstance(dob, datetime):
        dob = dob.date()
    if not isinstance(dob, date):
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def _collection_summary(country_id, loan_id):
    """(total_installments, overdue_installments) for one loan."""
    if not loan_id:
        return 0, 0
    row = _one(
        "SELECT COUNT(*) AS TotalInstallments, "
        "       SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END) AS OverdueInstallments "
        "FROM MfLoanCollection WHERE LoanId = %s AND CountryId = %s",
        [loan_id, country_id])
    if not row:
        return 0, 0
    return int(row.get('TotalInstallments') or 0), int(row.get('OverdueInstallments') or 0)


def build_scoring_data(member):
    """Assemble the dict calculate_credit_score() expects, from DW tables."""
    country_id = member.get('CountryId')
    member_id = member.get('MemberId')

    loans = _rows(
        "SELECT * FROM MfLoan WHERE MemberId = %s AND CountryId = %s ORDER BY Cycle DESC",
        [member_id, country_id])
    current_loan = loans[0] if loans else None
    prev_loan = loans[1] if len(loans) > 1 else None

    total_col, overdue_col = _collection_summary(
        country_id, current_loan.get('LoanId') if current_loan else None)
    if prev_loan:
        _, prev_overdue = _collection_summary(country_id, prev_loan.get('LoanId'))
    elif current_loan:
        prev_overdue = overdue_col
    else:
        prev_overdue = 0

    def guarantor(loan):
        if not loan:
            return None
        return _one(
            "SELECT TOP (1) FullName, ContactNumber, GrantorType FROM MfLoanGrantor "
            "WHERE LoanId = %s AND CountryId = %s", [loan.get('LoanId'), country_id])

    group = None
    group_count = 0
    if member.get('GroupId'):
        group = _one("SELECT * FROM MfGroup WHERE GroupId = %s AND CountryId = %s",
                     [member['GroupId'], country_id])
        row = _one(
            "SELECT COUNT(*) AS c FROM MfMember WHERE GroupId = %s AND CountryId = %s "
            "AND MemberStatus = 'Active'", [member['GroupId'], country_id])
        group_count = int(row['c']) if row else 0

    branch_id = current_loan.get('BranchId') if current_loan else None
    employee_id = current_loan.get('EmployeeId') if current_loan else None

    return {
        'member': member,
        'age': _age(member.get('DateOfBirth')),
        'loans': loans,
        'current_loan': current_loan,
        'loan_cycle': int((current_loan or {}).get('Cycle') or 0),
        'prev_overdue_count': prev_overdue,
        'total_collections': total_col,
        'overdue_collections': overdue_col,
        'current_guarantor': guarantor(current_loan),
        'prev_guarantor': guarantor(prev_loan),
        'group': group,
        'group_member_count': group_count,
        'mobile_changed': False,
        'additional_info': _one(
            "SELECT TOP (1) * FROM MfMemberAdditionalInfo "
            "WHERE MemberId = %s AND CountryId = %s",
            [member_id, country_id]) or {},
        'business': _one(
            "SELECT TOP (1) * FROM MfMemberBusiness WHERE MemberId = %s AND CountryId = %s",
            [member_id, country_id]) or {},
        'branch': _one("SELECT * FROM AdBranch WHERE BranchId = %s AND CountryId = %s",
                       [branch_id, country_id]) if branch_id else None,
        'branch_id': branch_id,
        'employee': _one("SELECT * FROM HrEmployee WHERE EmployeeId = %s AND CountryId = %s",
                         [employee_id, country_id]) if employee_id else None,
        'employee_id': employee_id,
    }


#  condition from loan + transaction history
def assess_condition(data):
    total = data.get('total_collections', 0)
    overdue = data.get('overdue_collections', 0)
    cycle = data.get('loan_cycle', 0)
    repay_rate = round((total - overdue) / total * 100, 1) if total else None

    if repay_rate is None:
        band, note = 'Unknown', 'No repayment history yet.'
    elif repay_rate >= 95 and overdue == 0:
        band, note = 'Strong', 'Consistently on-time repayments.'
    elif repay_rate >= 80:
        band, note = 'Fair', f'{overdue} overdue installment(s) — mostly on time.'
    else:
        band, note = 'Weak', f'{overdue} overdue installment(s), repayment {repay_rate}%.'

    cycle_note = (f'Repeat borrower (cycle {cycle}).' if cycle >= 2
                  else 'First-cycle borrower.' if cycle == 1 else 'No active loan cycle.')

    return {
        'band': band,
        'repayment_rate': repay_rate,
        'overdue_installments': overdue,
        'total_installments': total,
        'loan_cycle': cycle,
        'summary': f'{band} condition. {note} {cycle_note}',
    }


#  recommended loan amount (deterministic)
_MULT = {'Excellent': 1.5, 'Good': 1.25, 'Moderate Risk': 1.0, 'High Risk': 0.5}


def recommend_loan_amount(data, score_result):
    classification = score_result['classification']
    last_amount = float((data.get('current_loan') or {}).get('PrincipalAmount') or 0)

    total = data.get('total_collections', 0)
    overdue = data.get('overdue_collections', 0)
    overdue_ratio = (overdue / total) if total else 0.0

    mult = _MULT.get(classification, 1.0)
    if overdue_ratio > 0.30:
        mult *= 0.6
    elif overdue_ratio > 0.10:
        mult *= 0.8

    base = last_amount if last_amount > 0 else FIRST_CYCLE_BASE
    recommended = round(base * mult / 1000.0) * 1000 if base > 0 else 0

    if classification == 'High Risk':
        reasoning = ('High credit risk — recommend rejecting or lending a much '
                     'reduced, well-secured amount only.')
    elif last_amount <= 0:
        reasoning = ('First-time borrower — no prior loan to scale from; apply the '
                     'standard first-cycle policy amount.')
    else:
        reasoning = (f'Based on last loan {last_amount:,.0f} × {mult:.2f} '
                     f'({classification}, overdue ratio {overdue_ratio:.0%}).')

    return {'recommended_amount': recommended, 'multiplier': round(mult, 2),
            'based_on_last_amount': last_amount, 'amount_reasoning': reasoning}


def _decision(classification):
    return {
        'Excellent': 'Approve',
        'Good': 'Approve',
        'Moderate Risk': 'Conditional Approve',
        'High Risk': 'Reject',
    }.get(classification, 'Review')


def _suggestions(score_result, condition):
    """Deterministic, actionable suggestions from the weak scoring parameters —
    available even when the LLM is unavailable or weak."""
    tips = []
    for d in score_result['client_scoring']['details']:
        if d['score'] <= 2:
            tips.append(f"Improve {d['parameter'].lower()} ({d['reason']}).")
    if condition.get('overdue_installments'):
        tips.insert(0, "Clear overdue installments before increasing the loan size.")
    if not tips:
        tips.append("Strong profile — maintain the current repayment behaviour.")
    return tips[:5]


def _ai_narrative(score_result, condition, amount):
    weak = [f"- {d['parameter']}: {d['score']}/5 ({d['reason']})"
            for d in score_result['client_scoring']['details'] if d['score'] <= 2]
    prompt = f"""You are a microfinance credit officer. Write a short, clear assessment.

Member: {score_result['member_name']} ({score_result['member_code']})
Credit score: {score_result['percentage']}% — {score_result['classification']}
Financial condition: {condition['summary']}
Repayment rate: {condition['repayment_rate']}%  |  Overdue installments: {condition['overdue_installments']}
Suggested loan decision: {_decision(score_result['classification'])}
Suggested loan amount: {amount['recommended_amount']:,.0f} ({amount['amount_reasoning']})
Weak areas:
{chr(10).join(weak) if weak else '- None'}

In 4-6 sentences: assess the member's condition, justify the decision and the
suggested amount, and give 2-3 concrete suggestions to reduce risk."""

    result = llm.generate(prompt, model=ANALYSIS_MODEL, temperature=0.5, num_predict=400)
    if result['success'] and result['text']:
        return result['text'].strip()
    # Deterministic fallback if the model is unavailable.
    return (f"{score_result['member_name']} is {score_result['classification']} "
            f"({score_result['percentage']}%). {condition['summary']} "
            f"Decision: {_decision(score_result['classification'])}. "
            f"Suggested amount: {amount['recommended_amount']:,.0f}.")


# public entry point
def analyze_member(query, country=None):
    ref = extract_member_ref(query)
    matches = resolve_member(ref, country)
    if not matches:
        return {'success': False, 'mode': 'member_analysis',
                'error': f'No member found matching "{ref or query}".',
                'suggestions': suggest_members(query, country),
                'bad_request': True}

    member = matches[0]
    try:
        data = build_scoring_data(member)
        score_result = calculate_credit_score(data)
    except Exception as e:
        return {'success': False, 'mode': 'member_analysis',
                'error': f'Could not score this member: {e}'}

    condition = assess_condition(data)
    amount = recommend_loan_amount(data, score_result)
    decision = _decision(score_result['classification'])
    suggestions = _suggestions(score_result, condition)
    analysis = _ai_narrative(score_result, condition, amount)

    others = [f"{m.get('FirstName','')} {m.get('LastName','')} "
              f"({m.get('MemberCode','')}, {m.get('CountryCode','')})".strip()
              for m in matches[1:5]]

    # The same code exists in more than one country — say so, rather than let the
    # reader assume the assessment is about the person they had in mind.
    countries = {m.get('CountryCode') for m in matches}
    ambiguous = len(countries) > 1

    return {
        'success': True,
        'mode': 'member_analysis',
        'member': {
            'name': score_result['member_name'],
            'code': score_result['member_code'],
            'id': score_result['member_id'],
            'country': member.get('CountryCode'),
            'group': (data.get('group') or {}).get('GroupName', 'N/A'),
            'branch': (data.get('branch') or {}).get('BranchName', 'N/A'),
            'loan_officer': (data.get('employee') or {}).get('EmployeeName', 'N/A'),
        },
        'score': score_result['percentage'],
        'classification': score_result['classification'],
        'risk_level': score_result['risk_level'],
        'decision': decision,
        'condition_summary': condition['summary'],
        'condition': condition,
        'recommended_loan_amount': amount['recommended_amount'],
        'amount_reasoning': amount['amount_reasoning'],
        'suggestions': suggestions,
        'analysis': analysis,
        'score_detail': score_result['client_scoring'],
        'other_matches': others,
        'ambiguous_match': ambiguous,
        'match_note': (
            f"This code also exists in {', '.join(sorted(countries - {member.get('CountryCode')}))}. "
            f"Assessed the {member.get('CountryCode')} record — set a country to be explicit."
        ) if ambiguous else None,
    }
