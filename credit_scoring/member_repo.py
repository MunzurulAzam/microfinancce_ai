import pymssql
from datetime import datetime, date
from config import Config


def _get_connection():
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
    """Search for a member by name, MemberCode, or MemberId. Returns list of matching members."""
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        if query.strip().isdigit():
            cursor.execute(
                "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                "MemberStatus, DateOfBirth, IdNumber, GroupId "
                "FROM MfMember WHERE MemberId = %s", (int(query),)
            )
        elif query.strip().upper().startswith('CLN'):
            cursor.execute(
                "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                "MemberStatus, DateOfBirth, IdNumber, GroupId "
                "FROM MfMember WHERE MemberCode = %s", (query.strip(),)
            )
        else:
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
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        data = {}

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

        if member.get('DateOfBirth'):
            dob = member['DateOfBirth']
            if isinstance(dob, datetime):
                dob = dob.date()
            today = date.today()
            data['age'] = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        else:
            data['age'] = None

        group_id = member.get('GroupId')

        cursor.execute(
            "SELECT * FROM MfMemberAdditionalInfo WHERE MemberId = %s", (member_id,)
        )
        data['additional_info'] = cursor.fetchone() or {}

        cursor.execute(
            "SELECT * FROM MfMemberBusiness WHERE MemberId = %s", (member_id,)
        )
        data['business'] = cursor.fetchone() or {}

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

        if len(loans) >= 2:
            prev_loan_id = loans[1]['LoanId']
            cursor.execute(
                "SELECT COUNT(*) as overdue_count FROM MfLoanCollection "
                "WHERE LoanId = %s AND OverdueAmount > 0", (prev_loan_id,)
            )
            row = cursor.fetchone()
            data['prev_overdue_count'] = row['overdue_count'] if row else 0
        elif len(loans) == 1:
            cursor.execute(
                "SELECT COUNT(*) as overdue_count FROM MfLoanCollection "
                "WHERE LoanId = %s AND OverdueAmount > 0", (loans[0]['LoanId'],)
            )
            row = cursor.fetchone()
            data['prev_overdue_count'] = row['overdue_count'] if row else 0
        else:
            data['prev_overdue_count'] = 0

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

        data['mobile_changed'] = False
        if member.get('ContactNumber') and len(loans) >= 2:
            data['mobile_changed'] = False

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

        return data

    finally:
        conn.close()
