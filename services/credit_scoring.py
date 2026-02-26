"""
Credit Scoring system start
"""

from decimal import Decimal


def _to_float(val):
    """Safely convert Decimal / str / None to float."""
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0



#!--------- CLIENT CREDIT SCORING


def _score_overdue(data):
    """1. Overdue (Previous Loan Cycle)"""
    cnt = data.get('prev_overdue_count', 0)
    if cnt == 0:
        return 5, "No overdue"
    elif cnt == 1:
        return 3, "One installment overdue"
    else:
        return 0, f"{cnt} installments overdue"


def _score_loan_cycle(data):
    """2. Loan Cycle"""
    cycle = data.get('loan_cycle', 0)
    if cycle >= 4:
        return 5, f"Cycle {cycle} (4th+)"
    elif cycle >= 2:
        return 4, f"Cycle {cycle} (2nd-3rd)"
    else:
        return 3, f"Cycle {cycle} (1st)"


def _score_guarantor_same(data):
    """3. Guarantor — same or changed"""
    curr = data.get('current_guarantor')
    prev = data.get('prev_guarantor')
    if not curr or not prev:
        return 4, "No previous guarantor data"
    if curr.get('FullName', '').strip().lower() == prev.get('FullName', '').strip().lower():
        return 5, "Same guarantor as previous cycle"
    return 4, "Changed guarantor"


def _score_guarantor_job(data):
    """4. Guarantor Job Status"""
    curr = data.get('current_guarantor')
    if not curr:
        return 3, "No guarantor data"
    gtype = (curr.get('GrantorType') or '').lower()
    if gtype in ('family member', 'spouse', 'relative'):
        return 5, f"Stable ({curr.get('GrantorType')})"
    elif gtype in ('group member', 'friend'):
        return 3, f"Unstable ({curr.get('GrantorType')})"
    return 3, f"Unknown ({curr.get('GrantorType', 'N/A')})"


def _score_repayment_history(data):
    """5. Repayment History"""
    total = data.get('total_collections', 0)
    overdue = data.get('overdue_collections', 0)
    if total == 0:
        return 3, "No repayment history"
    if overdue == 0:
        return 5, "Always timely"
    elif overdue <= 2:
        return 4, f"Delayed {overdue} time(s)"
    else:
        return 2, f"Delayed {overdue} times"


def _score_meeting_attendance(data):
    """6. Group Meeting Attendance — estimated from collection regularity"""
    total = data.get('total_collections', 0)
    overdue = data.get('overdue_collections', 0)
    if total == 0:
        return 3, "No attendance data"
    attendance_rate = ((total - overdue) / total) * 100
    if attendance_rate >= 90:
        return 5, f"~{attendance_rate:.0f}% attendance"
    elif attendance_rate >= 75:
        return 4, f"~{attendance_rate:.0f}% attendance"
    elif attendance_rate >= 50:
        return 3, f"~{attendance_rate:.0f}% attendance"
    else:
        return 0, f"~{attendance_rate:.0f}% attendance"


def _score_group_size(data):
    """7. Group Size"""
    count = data.get('group_member_count', 0)
    if count >= 15:
        return 5, f"{count} members"
    elif count >= 10:
        return 4, f"{count} members"
    else:
        return 2, f"{count} members"


def _score_mobile_number(data):
    """8. Mobile Number — same or changed"""
    if data.get('mobile_changed'):
        return 3, "Mobile number changed"
    return 5, "Same mobile number"


def _score_residence(data):
    """9. Stability of Residence"""
    ai = data.get('additional_info', {})
    val = (ai.get('StabilityResidence') or '').lower().strip()
    if val in ('own', 'own house'):
        return 5, "Own house"
    elif 'rent' in val and ('1' in val or 'year' in val or 'more' in val):
        return 4, f"Rented ({val})"
    elif 'rent' in val:
        return 2, f"Rented ({val})"
    elif val:
        return 4, val.title()
    return 3, "Unknown"


def _score_business_permit(data):
    """10. Business Permit"""
    ai = data.get('additional_info', {})
    val = (ai.get('BusinessPermits') or '').lower()
    if 'with' in val and 'without' not in val:
        return 5, "With license/permit"
    return 3, "Without license/permit"


def _score_alt_income(data):
    """11. Alternative Income Source"""
    ai = data.get('additional_info', {})
    val = (ai.get('AltSourceOfIncome') or '').lower()
    if val == 'yes':
        return 5, "Has alternative income"
    return 3, "No alternative income"


def _score_daily_sales(data):
    """12. Daily Sales"""
    ai = data.get('additional_info', {})
    val = (ai.get('DailySalesAmount') or '').lower()
    if 'more' in val:
        return 5, "Sales ≥ installment"
    return 3, "Sales < installment"


def _score_income_vs_expenses(data):
    """13. Monthly Income vs Expenses"""
    biz = data.get('business', {})
    income_str = biz.get('MonthlyIncome', '0')
    try:
        income = float(income_str)
    except (ValueError, TypeError):
        income = 0
    loan_amount = _to_float((data.get('current_loan') or {}).get('PrincipalAmount'))
    if income > 0 and loan_amount > 0:
        if income >= loan_amount:
            return 5, f"Income ({income:,.0f}) ≥ Loan ({loan_amount:,.0f})"
        return 3, f"Income ({income:,.0f}) < Loan ({loan_amount:,.0f})"
    return 3, "No income data"


def _score_mobile_money(data):
    """14. Mobile Money / Bank Account"""
    ai = data.get('additional_info', {})
    val = (ai.get('MobileMoneyBankAccount') or '').lower()
    if val == 'yes':
        return 5, "Has mobile money/bank account"
    return 3, "No mobile money/bank account"


def _score_client_age(data):
    """15. Client Age"""
    age = data.get('age')
    if age is None:
        return 3, "Age unknown"
    if 18 <= age <= 60:
        return 5, f"Age {age} (18-60)"
    return 0, f"Age {age} (outside 18-60)"


def _score_employment_gen(data):
    """16. Employment Generation"""
    ai = data.get('additional_info', {})
    val = (ai.get('EmploymentGenerating') or '').lower()
    if val in ('one or more', 'yes', 'has employee', 'has employees'):
        return 5, "Has employee(s)"
    return 4, "No employee"


def _score_attitude(data):
    """17. Attitude Toward Institution"""
    ai = data.get('additional_info', {})
    val = (ai.get('AttitudeUmoja') or '').lower()
    if val == 'positive':
        return 5, "Positive attitude"
    elif val == 'mixed':
        return 3, "Mixed attitude"
    elif val == 'negative':
        return 0, "Negative attitude"
    return 3, "Unknown"


def _score_pep(data):
    """18. Politically Exposed Person"""
    ai = data.get('additional_info', {})
    val = (ai.get('MemberPoliticallyExposed') or '').lower()
    if val == 'yes':
        return 0, "⚠️ Politically Exposed"
    return 5, "Not politically exposed"


def _score_other_mfi(data):
    """19. Loan with Other MFI"""
    ai = data.get('additional_info', {})
    val = (ai.get('HasLoanWithOtherMfi') or '').lower()
    if val == 'yes':
        return 3, "Has loan with other MFI"
    return 5, "No loan with other MFI"


def _score_national_id(data):
    """20. Valid National ID"""
    member = data.get('member', {})
    id_num = (member.get('IdNumber') or '').strip()
    if id_num and len(id_num) > 3:
        return 5, f"Valid ID: {id_num[:6]}..."
    return 0, "No valid National ID"


def _score_social_media(data):
    """21. Social Media Account"""
    ai = data.get('additional_info', {})
    val = (ai.get('HasSocialMediaAccount') or '').lower()
    if val == 'yes':
        return 5, "Has social media"
    return 3, "No social media"



# BRANCH / BRANCH MANAGER PERFORMANCE

def _score_branch_borrower_growth(data):
    """Borrower Growth Per Month"""
    perf = data.get('branch_performance')
    if not perf:
        return 3, "No performance data"
    new_admissions = perf.get('NoOfNewAdmission', 0) or 0
    if new_admissions >= 20:
        return 5, f"{new_admissions} new admissions"
    elif new_admissions >= 15:
        return 4, f"{new_admissions} new admissions"
    elif new_admissions >= 10:
        return 3, f"{new_admissions} new admissions"
    elif new_admissions >= 5:
        return 2, f"{new_admissions} new admissions"
    else:
        return 0, f"{new_admissions} new admissions (reduced)"


def _score_branch_target(data):
    """Borrower Target vs Achievement"""
    perf = data.get('branch_performance')
    if not perf:
        return 3, "No target data"
    disbursed = perf.get('NoOfTotalDisburse', 0) or 0
    if disbursed >= 50:
        return 5, f"{disbursed} disbursements"
    elif disbursed >= 40:
        return 4, f"{disbursed} disbursements"
    elif disbursed >= 30:
        return 3, f"{disbursed} disbursements"
    elif disbursed >= 20:
        return 2, f"{disbursed} disbursements"
    else:
        return 1, f"{disbursed} disbursements"


def _score_branch_par(data):
    """PAR > 30 Days"""
    total = data.get('branch_total_active_loans', 0)
    par = data.get('branch_par_loans', 0)
    if total == 0:
        return 3, "No active loans"
    par_rate = (par / total) * 100
    if par_rate == 0:
        return 5, "0% PAR"
    elif par_rate < 1:
        return 4, f"{par_rate:.2f}% PAR"
    elif par_rate < 2:
        return 3, f"{par_rate:.2f}% PAR"
    elif par_rate < 3:
        return 2, f"{par_rate:.2f}% PAR"
    else:
        return 1, f"{par_rate:.2f}% PAR"


def _score_branch_staff_dropout(data):
    """Staff Dropout (Yearly) — estimated"""
    # Without direct staff dropout data, use a neutral score
    return 4, "Staff dropout data not tracked"


def _score_branch_client_dropout(data):
    """Client Dropout (Yearly) — estimated"""
    return 4, "Client dropout data not tracked"



# LOAN OFFICER PERFORMANCE  (6 parameters, max 30)
def _score_lo_borrower_growth(data):
    """LO Borrower Growth"""
    perf = data.get('lo_performance')
    if not perf:
        return 3, "No LO performance data"
    new_borrowers = perf.get('NoOfNewBorrower_Cycle_1', 0) or 0
    if new_borrowers >= 10:
        return 5, f"{new_borrowers} new cycle-1 borrowers"
    elif new_borrowers >= 7:
        return 4, f"{new_borrowers} new cycle-1 borrowers"
    elif new_borrowers >= 5:
        return 3, f"{new_borrowers} new cycle-1 borrowers"
    elif new_borrowers >= 3:
        return 2, f"{new_borrowers} new cycle-1 borrowers"
    else:
        return 0, f"{new_borrowers} new cycle-1 borrowers"


def _score_lo_target(data):
    """LO Target vs Achievement"""
    perf = data.get('lo_performance')
    if not perf:
        return 3, "No LO target data"
    disbursed = perf.get('NoOfTotalDisburse', 0) or 0
    if disbursed >= 25:
        return 5, f"{disbursed} disbursements"
    elif disbursed >= 20:
        return 4, f"{disbursed} disbursements"
    elif disbursed >= 15:
        return 3, f"{disbursed} disbursements"
    elif disbursed >= 10:
        return 2, f"{disbursed} disbursements"
    else:
        return 1, f"{disbursed} disbursements"


def _score_lo_par(data):
    """LO PAR > 30 Days — Special: if PAR increases → 0"""
    total = data.get('lo_total_active_loans', 0)
    par = data.get('lo_par_loans', 0)
    if total == 0:
        return 3, "No active loans"
    par_rate = (par / total) * 100
    if par_rate == 0:
        return 5, "0% PAR"
    elif par_rate < 1:
        return 4, f"{par_rate:.2f}% PAR"
    elif par_rate < 2:
        return 3, f"{par_rate:.2f}% PAR"
    elif par_rate < 3:
        return 2, f"{par_rate:.2f}% PAR"
    else:
        return 1, f"{par_rate:.2f}% PAR"


def _score_lo_staff_dropout(data):
    """LO area staff dropout"""
    return 4, "Staff dropout data not tracked"


def _score_lo_client_dropout(data):
    """LO area client dropout"""
    return 4, "Client dropout data not tracked"


def _score_lo_group_size(data):
    """Group Size per LO"""
    lo_members = data.get('lo_total_members', 0)
    lo_groups = data.get('lo_group_count', 1)
    if lo_groups == 0:
        lo_groups = 1
    avg = lo_members / lo_groups
    if 21 <= avg <= 25:
        return 5, f"Avg {avg:.0f} members/group"
    elif 16 <= avg <= 20:
        return 4, f"Avg {avg:.0f} members/group"
    elif 11 <= avg <= 15:
        return 3, f"Avg {avg:.0f} members/group"
    elif avg == 10:
        return 2, f"Avg {avg:.0f} members/group"
    elif avg > 25:
        return 5, f"Avg {avg:.0f} members/group (large)"
    else:
        return 1, f"Avg {avg:.0f} members/group"


# MAIN SCORING FUNCTION

CLIENT_SCORING_FUNCS = [
    ("Overdue (Previous Loan)", _score_overdue),
    ("Loan Cycle", _score_loan_cycle),
    ("Guarantor Consistency", _score_guarantor_same),
    ("Guarantor Job Status", _score_guarantor_job),
    ("Repayment History", _score_repayment_history),
    ("Meeting Attendance", _score_meeting_attendance),
    ("Group Size", _score_group_size),
    ("Mobile Number Stability", _score_mobile_number),
    ("Stability of Residence", _score_residence),
    ("Business Permit", _score_business_permit),
    ("Alternative Income", _score_alt_income),
    ("Daily Sales", _score_daily_sales),
    ("Income vs Expenses", _score_income_vs_expenses),
    ("Mobile Money / Bank", _score_mobile_money),
    ("Client Age", _score_client_age),
    ("Employment Generation", _score_employment_gen),
    ("Attitude Toward Institution", _score_attitude),
    ("Politically Exposed (PEP)", _score_pep),
    ("Loan with Other MFI", _score_other_mfi),
    ("Valid National ID", _score_national_id),
    ("Social Media Account", _score_social_media),
]

BRANCH_SCORING_FUNCS = [
    ("Borrower Growth/Month", _score_branch_borrower_growth),
    ("Target vs Achievement", _score_branch_target),
    ("PAR > 30 Days", _score_branch_par),
    ("Staff Dropout", _score_branch_staff_dropout),
    ("Client Dropout", _score_branch_client_dropout),
]

LO_SCORING_FUNCS = [
    ("LO Borrower Growth", _score_lo_borrower_growth),
    ("LO Target Achievement", _score_lo_target),
    ("LO PAR > 30 Days", _score_lo_par),
    ("LO Staff Dropout", _score_lo_staff_dropout),
    ("LO Client Dropout", _score_lo_client_dropout),
    ("Group Size per LO", _score_lo_group_size),
]


def calculate_credit_score(data):
    """
    Calculate the full credit score for a member.
    Returns a structured result with breakdown.
    """
    client_details = []
    client_total = 0
    client_max = len(CLIENT_SCORING_FUNCS) * 5

    for name, func in CLIENT_SCORING_FUNCS:
        score, reason = func(data)
        client_details.append({
            'parameter': name,
            'score': score,
            'max': 5,
            'reason': reason
        })
        client_total += score

    branch_details = []
    branch_total = 0
    branch_max = len(BRANCH_SCORING_FUNCS) * 5

    for name, func in BRANCH_SCORING_FUNCS:
        score, reason = func(data)
        branch_details.append({
            'parameter': name,
            'score': score,
            'max': 5,
            'reason': reason
        })
        branch_total += score

    lo_details = []
    lo_total = 0
    lo_max = len(LO_SCORING_FUNCS) * 5

    for name, func in LO_SCORING_FUNCS:
        score, reason = func(data)
        lo_details.append({
            'parameter': name,
            'score': score,
            'max': 5,
            'reason': reason
        })
        lo_total += score

    # Overall
    total_score = client_total + branch_total + lo_total
    max_score = client_max + branch_max + lo_max
    percentage = (total_score / max_score) * 100 if max_score > 0 else 0

    # Classification
    if percentage >= 85:
        classification = 'Excellent'
        risk_level = 'low'
    elif percentage >= 70:
        classification = 'Good'
        risk_level = 'low-moderate'
    elif percentage >= 50:
        classification = 'Moderate Risk'
        risk_level = 'moderate'
    else:
        classification = 'High Risk'
        risk_level = 'high'

    member = data.get('member', {})

    return {
        'member_name': f"{member.get('FirstName', '')} {member.get('LastName', '')}".strip(),
        'member_code': member.get('MemberCode', ''),
        'member_id': member.get('MemberId', ''),

        'total_score': total_score,
        'max_score': max_score,
        'percentage': round(percentage, 1),
        'classification': classification,
        'risk_level': risk_level,

        'client_scoring': {
            'score': client_total,
            'max': client_max,
            'percentage': round((client_total / client_max) * 100, 1) if client_max > 0 else 0,
            'details': client_details
        },
        'branch_scoring': {
            'score': branch_total,
            'max': branch_max,
            'percentage': round((branch_total / branch_max) * 100, 1) if branch_max > 0 else 0,
            'details': branch_details,
            'branch_name': (data.get('branch') or {}).get('BranchName', 'N/A')
        },
        'lo_scoring': {
            'score': lo_total,
            'max': lo_max,
            'percentage': round((lo_total / lo_max) * 100, 1) if lo_max > 0 else 0,
            'details': lo_details,
            'lo_name': (data.get('employee') or {}).get('EmployeeName', 'N/A')
        }
    }
