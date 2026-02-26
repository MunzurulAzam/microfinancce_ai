"""
MSSQL Database Connector
Fetches client, branch, and loan officer data for credit scoring
"""

import pymssql
from datetime import datetime, date
from config import Config


def _get_connection():
    """Create a new MSSQL connection."""
    return pymssql.connect(
        server=Config.MSSQL_SERVER,
        port=Config.MSSQL_PORT,
        user=Config.MSSQL_USER,
        password=Config.MSSQL_PASSWORD,
        database=Config.MSSQL_DATABASE,
        login_timeout=15,
        as_dict=True
    )


def search_member(query):
    """
    Search for a member by name, MemberCode, or MemberId.
    Returns list of matching members.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        # Try MemberId (numeric)
        if query.strip().isdigit():
            cursor.execute(
                "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                "MemberStatus, DateOfBirth, IdNumber, GroupId "
                "FROM MfMember WHERE MemberId = %s", (int(query),)
            )
        # Try MemberCode (starts with CLN)
        elif query.strip().upper().startswith('CLN'):
            cursor.execute(
                "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                "MemberStatus, DateOfBirth, IdNumber, GroupId "
                "FROM MfMember WHERE MemberCode = %s", (query.strip(),)
            )
        else:
            # Search by name
            parts = query.strip().split()
            if len(parts) >= 2:
                cursor.execute(
                    "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                    "MemberStatus, DateOfBirth, IdNumber, GroupId "
                    "FROM MfMember WHERE (FirstName LIKE %s AND LastName LIKE %s) "
                    "OR (FirstName LIKE %s AND LastName LIKE %s) "
                    "ORDER BY MemberStatus DESC",
                    (f'%{parts[0]}%', f'%{parts[1]}%', f'%{parts[1]}%', f'%{parts[0]}%')
                )
            else:
                cursor.execute(
                    "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                    "MemberStatus, DateOfBirth, IdNumber, GroupId "
                    "FROM MfMember WHERE FirstName LIKE %s OR LastName LIKE %s "
                    "ORDER BY MemberStatus DESC",
                    (f'%{query}%', f'%{query}%')
                )

        results = cursor.fetchall()
        return results
    finally:
        conn.close()


def get_member_full_data(member_id):
    """
    Fetch all data needed for credit scoring for a given member.
    Returns a dict with all scoring-relevant data.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        data = {}

        # ── 1. Member basic info ──
        cursor.execute(
            "SELECT MemberId, FirstName, LastName, MemberCode, ContactNumber, "
            "MemberStatus, DateOfBirth, IdNumber, GroupId, Gender, Occupation, "
            "MaritalStatus, Address "
            "FROM MfMember WHERE MemberId = %s", (member_id,)
        )
        member = cursor.fetchone()
        if not member:
            return None
        data['member'] = member

        # Calculate age
        if member.get('DateOfBirth'):
            dob = member['DateOfBirth']
            if isinstance(dob, datetime):
                dob = dob.date()
            today = date.today()
            data['age'] = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        else:
            data['age'] = None

        group_id = member.get('GroupId')

        # ── 2. Additional info (scoring fields) ──
        cursor.execute(
            "SELECT * FROM MfMemberAdditionalInfo WHERE MemberId = %s", (member_id,)
        )
        data['additional_info'] = cursor.fetchone() or {}

        # ── 3. Business info ──
        cursor.execute(
            "SELECT * FROM MfMemberBusiness WHERE MemberId = %s", (member_id,)
        )
        data['business'] = cursor.fetchone() or {}

        # ── 4. All loans (for cycle, overdue history) ──
        cursor.execute(
            "SELECT LoanId, Cycle, PrincipalAmount, InstallmentAmount, LoanStatus, "
            "DisburseDate, GroupId, EmployeeId, BranchId, PrincipalOutstanding, "
            "InterestOutstanding, TotalOutstanding "
            "FROM MfLoan WHERE MemberId = %s ORDER BY Cycle DESC", (member_id,)
        )
        loans = cursor.fetchall()
        data['loans'] = loans
        data['current_loan'] = loans[0] if loans else None
        data['loan_cycle'] = loans[0]['Cycle'] if loans else 0

        # ── 5. Overdue count for previous loan cycle ──
        if len(loans) >= 2:
            prev_loan_id = loans[1]['LoanId']
            cursor.execute(
                "SELECT COUNT(*) as overdue_count FROM MfLoanCollection "
                "WHERE LoanId = %s AND OverdueAmount > 0", (prev_loan_id,)
            )
            row = cursor.fetchone()
            data['prev_overdue_count'] = row['overdue_count'] if row else 0
        elif len(loans) == 1:
            # First loan — check overdue on current
            cursor.execute(
                "SELECT COUNT(*) as overdue_count FROM MfLoanCollection "
                "WHERE LoanId = %s AND OverdueAmount > 0", (loans[0]['LoanId'],)
            )
            row = cursor.fetchone()
            data['prev_overdue_count'] = row['overdue_count'] if row else 0
        else:
            data['prev_overdue_count'] = 0

        # ── 6. Repayment history (current or most recent loan) ──
        if loans:
            latest_loan_id = loans[0]['LoanId']
            cursor.execute(
                "SELECT COUNT(*) as total_collections, "
                "SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END) as overdue_collections "
                "FROM MfLoanCollection WHERE LoanId = %s", (latest_loan_id,)
            )
            rep = cursor.fetchone()
            data['total_collections'] = rep['total_collections'] if rep else 0
            data['overdue_collections'] = rep['overdue_collections'] if rep else 0
        else:
            data['total_collections'] = 0
            data['overdue_collections'] = 0

        # ── 7. Guarantor info (current + previous) ──
        if loans:
            current_loan_id = loans[0]['LoanId']
            cursor.execute(
                "SELECT FullName, ContactNumber, GrantorType FROM MfLoanGrantor "
                "WHERE LoanId = %s", (current_loan_id,)
            )
            data['current_guarantor'] = cursor.fetchone()

            if len(loans) >= 2:
                prev_loan_id = loans[1]['LoanId']
                cursor.execute(
                    "SELECT FullName, ContactNumber, GrantorType FROM MfLoanGrantor "
                    "WHERE LoanId = %s", (prev_loan_id,)
                )
                data['prev_guarantor'] = cursor.fetchone()
            else:
                data['prev_guarantor'] = None
        else:
            data['current_guarantor'] = None
            data['prev_guarantor'] = None

        # ── 8. Group info & member count ──
        if group_id:
            cursor.execute(
                "SELECT GroupId, GroupName, EmployeeId, BranchId FROM MfGroup "
                "WHERE GroupId = %s", (group_id,)
            )
            data['group'] = cursor.fetchone()

            cursor.execute(
                "SELECT COUNT(*) as member_count FROM MfMember "
                "WHERE GroupId = %s AND MemberStatus = 'Active'", (group_id,)
            )
            row = cursor.fetchone()
            data['group_member_count'] = row['member_count'] if row else 0
        else:
            data['group'] = None
            data['group_member_count'] = 0

        # ── 9. Mobile number change (compare across loan cycles) ──
        data['mobile_changed'] = False
        if member.get('ContactNumber') and len(loans) >= 2:
            # We can't directly compare phone across cycles in MfMember (single row),
            # so we assume same if only 1 member record exists
            data['mobile_changed'] = False

        # ── 10. Branch info ──
        branch_id = loans[0]['BranchId'] if loans else (data['group'] or {}).get('BranchId')
        if branch_id:
            cursor.execute(
                "SELECT BranchId, BranchName, BranchCode, StartDate FROM AdBranch "
                "WHERE BranchId = %s", (branch_id,)
            )
            data['branch'] = cursor.fetchone()
        else:
            data['branch'] = None
        data['branch_id'] = branch_id

        # ── 11. Employee / Loan Officer info ──
        employee_id = loans[0]['EmployeeId'] if loans else (data['group'] or {}).get('EmployeeId')
        if employee_id:
            cursor.execute(
                "SELECT EmployeeId, EmployeeName, DesignationId, BranchId "
                "FROM HrEmployee WHERE EmployeeId = %s", (employee_id,)
            )
            data['employee'] = cursor.fetchone()
        else:
            data['employee'] = None
        data['employee_id'] = employee_id

        # ── 12. Branch performance data ──
        if branch_id:
            # Total borrowers in this branch
            cursor.execute(
                "SELECT COUNT(DISTINCT m.MemberId) as total_borrowers "
                "FROM MfLoan l JOIN MfMember m ON l.MemberId = m.MemberId "
                "WHERE l.BranchId = %s AND l.LoanStatus = 1", (branch_id,)
            )
            row = cursor.fetchone()
            data['branch_total_borrowers'] = row['total_borrowers'] if row else 0

            # PAR > 30 days for this branch
            cursor.execute(
                "SELECT COUNT(*) as overdue_loans FROM MfLoan "
                "WHERE BranchId = %s AND LoanStatus = 1 AND PrincipalOutstanding > 0",
                (branch_id,)
            )
            row = cursor.fetchone()
            data['branch_total_active_loans'] = row['overdue_loans'] if row else 0

            # Overdue loans in branch (PAR proxy)
            cursor.execute(
                "SELECT COUNT(DISTINCT l.LoanId) as par_loans "
                "FROM MfLoan l "
                "JOIN MfLoanCollection lc ON l.LoanId = lc.LoanId "
                "WHERE l.BranchId = %s AND l.LoanStatus = 1 "
                "AND lc.OverdueAmount > 0 AND lc.IsNewOverdue = 1",
                (branch_id,)
            )
            row = cursor.fetchone()
            data['branch_par_loans'] = row['par_loans'] if row else 0

            # Branch performance tracker (latest)
            cursor.execute(
                "SELECT TOP 1 * FROM MfPerformanceTrackerData "
                "WHERE BranchId = %s ORDER BY BusinessDate DESC", (branch_id,)
            )
            data['branch_performance'] = cursor.fetchone()
        else:
            data['branch_total_borrowers'] = 0
            data['branch_total_active_loans'] = 0
            data['branch_par_loans'] = 0
            data['branch_performance'] = None

        # ── 13. LO performance data ──
        if employee_id:
            # Groups per LO
            cursor.execute(
                "SELECT COUNT(*) as group_count FROM MfGroup "
                "WHERE EmployeeId = %s AND GroupStatus = 'Active'", (employee_id,)
            )
            row = cursor.fetchone()
            data['lo_group_count'] = row['group_count'] if row else 0

            # Total members per LO
            cursor.execute(
                "SELECT COUNT(DISTINCT m.MemberId) as member_count "
                "FROM MfGroup g JOIN MfMember m ON g.GroupId = m.GroupId "
                "WHERE g.EmployeeId = %s AND g.GroupStatus = 'Active' AND m.MemberStatus = 'Active'",
                (employee_id,)
            )
            row = cursor.fetchone()
            data['lo_total_members'] = row['member_count'] if row else 0

            # LO PAR
            cursor.execute(
                "SELECT COUNT(DISTINCT l.LoanId) as par_loans "
                "FROM MfLoan l "
                "JOIN MfLoanCollection lc ON l.LoanId = lc.LoanId "
                "WHERE l.EmployeeId = %s AND l.LoanStatus = 1 "
                "AND lc.OverdueAmount > 0 AND lc.IsNewOverdue = 1",
                (employee_id,)
            )
            row = cursor.fetchone()
            data['lo_par_loans'] = row['par_loans'] if row else 0

            cursor.execute(
                "SELECT COUNT(*) as total_active FROM MfLoan "
                "WHERE EmployeeId = %s AND LoanStatus = 1", (employee_id,)
            )
            row = cursor.fetchone()
            data['lo_total_active_loans'] = row['total_active'] if row else 0

            # LO performance tracker
            cursor.execute(
                "SELECT TOP 1 * FROM MfPerformanceTrackerData "
                "WHERE Loid = %s ORDER BY BusinessDate DESC", (employee_id,)
            )
            data['lo_performance'] = cursor.fetchone()
        else:
            data['lo_group_count'] = 0
            data['lo_total_members'] = 0
            data['lo_par_loans'] = 0
            data['lo_total_active_loans'] = 0
            data['lo_performance'] = None

        return data

    finally:
        conn.close()
