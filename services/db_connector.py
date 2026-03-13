"""
MSSQL Database Connector
Fetches client, branch, and loan officer data for credit scoring
"""

import pymssql
from datetime import datetime, date
from config import Config


def _get_connection():
    """Create a new MSSQL connection.
    For Windows Authentication (Trusted_Connection=True), uses pyodbc.
    For SQL Auth, uses pyodbc first then pymssql as fallback.
    """
    conn_str = getattr(Config, 'MSSQL_CONNECTION_STRING', None)

    if conn_str:
        # Parse connection string params
        params = {}
        for part in conn_str.split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k.strip().lower()] = v.strip()

        trusted = params.get('trusted_connection', 'false').lower() in ('true', 'yes')

        # --- Always try pyodbc first (required for Windows Auth) ---
        try:
            import pyodbc
            available_drivers = pyodbc.drivers()
            print(f"[db_connector] Available ODBC drivers: {available_drivers}")

            driver = None
            for d in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server',
                      'SQL Server Native Client 11.0', 'SQL Server']:
                if d in available_drivers:
                    driver = f"{{{d}}}"
                    break

            if driver is None:
                raise RuntimeError(f"No SQL Server ODBC driver found. Install 'ODBC Driver 17 for SQL Server'. Available: {available_drivers}")

            # Build pyodbc connection string (driver already has braces)
            if 'driver=' not in conn_str.lower():
                full_conn_str = f"DRIVER={driver};{conn_str}"
            else:
                full_conn_str = conn_str

            # Normalize ADO.NET keywords and boolean values to ODBC format
            import re
            full_conn_str = re.sub(r'(?i)Data Source=', 'SERVER=', full_conn_str)
            full_conn_str = re.sub(r'(?i)Initial Catalog=', 'DATABASE=', full_conn_str)
            full_conn_str = re.sub(r'(?i)Trusted_Connection=True', 'Trusted_Connection=yes', full_conn_str)
            full_conn_str = re.sub(r'(?i)Trusted_Connection=False', 'Trusted_Connection=no', full_conn_str)
            full_conn_str = re.sub(r'(?i)TrustServerCertificate=True', 'TrustServerCertificate=yes', full_conn_str)
            full_conn_str = re.sub(r'(?i)TrustServerCertificate=False', 'TrustServerCertificate=no', full_conn_str)
            
            # Remove unsupported ADO.NET-only attributes
            for attr in ['Pooling', 'Max Pool Size', 'MultipleActiveResultSets']:
                full_conn_str = re.sub(rf'(?i){re.escape(attr)}=[^;]+;?', '', full_conn_str)

            print(f"[db_connector] Connecting via pyodbc with driver: {driver}")
            conn = pyodbc.connect(full_conn_str, timeout=15)
            print("[db_connector] pyodbc connection successful!")
            return conn

        except ImportError:
            if trusted:
                raise RuntimeError(
                    "pyodbc is not installed but Windows Auth (Trusted_Connection=True) requires it. "
                    "Run: pip install pyodbc"
                )
            print("[db_connector] pyodbc not installed, falling back to pymssql (SQL Auth only)")
        except Exception as e:
            print(f"[db_connector] pyodbc failed: {e}")
            if trusted:
                raise RuntimeError(
                    f"Windows Authentication requires pyodbc, but it failed: {e}. "
                    "Check that 'ODBC Driver 17 for SQL Server' is installed on this server."
                )

        # --- pymssql fallback (SQL Server Auth only, not Windows Auth) ---
        server = params.get('data source', params.get('server', ''))
        database = params.get('initial catalog', params.get('database', ''))

        # Parse port from server string (e.g. host,port)
        port = 1433
        if ',' in server:
            server, port_str = server.split(',', 1)
            try: port = int(port_str.strip())
            except: pass
        elif ':' in server and not server.startswith('['):
            server, port_str = server.split(':', 1)
            try: port = int(port_str.strip())
            except: pass

        user = params.get('user id', params.get('uid', ''))
        password = params.get('password', params.get('pwd', ''))
        return pymssql.connect(
            server=server, port=port, user=user, password=password,
            database=database, login_timeout=15, as_dict=True
        )

    # 2. Fallback to individual legacy vars
    server = getattr(Config, 'MSSQL_SERVER', None)
    if not server:
        raise ValueError("MSSQL Database connection failed: No valid connection string or fallback server configuration found.")

    return pymssql.connect(
        server=server,
        port=getattr(Config, 'MSSQL_PORT', 1433),
        user=getattr(Config, 'MSSQL_USER', ''),
        password=getattr(Config, 'MSSQL_PASSWORD', ''),
        database=getattr(Config, 'MSSQL_DATABASE', ''),
        login_timeout=15,
        as_dict=True
    )


def _row_to_dict(cursor, row):
    """Convert a single Row result to a dict (for pyodbc)."""
    if row is None: return None
    # If it's already a dict (from pymssql), return it
    if isinstance(row, dict): return row
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def _rows_to_dicts(cursor, rows):
    """Convert a list of Row results to dicts (for pyodbc)."""
    if not rows: return []
    # If they are already dicts (from pymssql), return them
    if rows and isinstance(rows[0], dict): return rows
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]



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
                "FROM MfMember WHERE MemberId = ?", (int(query),)
            )
        # Try MemberCode (starts with CLN)
        elif query.strip().upper().startswith('CLN'):
            cursor.execute(
                "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                "MemberStatus, DateOfBirth, IdNumber, GroupId "
                "FROM MfMember WHERE MemberCode = ?", (query.strip(),)
            )
        else:
            # Search by name
            parts = query.strip().split()
            if len(parts) >= 2:
                cursor.execute(
                    "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                    "MemberStatus, DateOfBirth, IdNumber, GroupId "
                    "FROM MfMember WHERE (FirstName LIKE ? AND LastName LIKE ?) "
                    "OR (FirstName LIKE ? AND LastName LIKE ?) "
                    "ORDER BY MemberStatus DESC",
                    (f'%{parts[0]}%', f'%{parts[1]}%', f'%{parts[1]}%', f'%{parts[0]}%')
                )
            else:
                cursor.execute(
                    "SELECT TOP 10 MemberId, FirstName, LastName, MemberCode, ContactNumber, "
                    "MemberStatus, DateOfBirth, IdNumber, GroupId "
                    "FROM MfMember WHERE FirstName LIKE ? OR LastName LIKE ? "
                    "ORDER BY MemberStatus DESC",
                    (f'%{query}%', f'%{query}%')
                )

        results = cursor.fetchall()
        return _rows_to_dicts(cursor, results)
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

        # --------- Member basic info
        cursor.execute(
            "SELECT MemberId, FirstName, LastName, MemberCode, ContactNumber, "
            "MemberStatus, DateOfBirth, IdNumber, GroupId, Gender, Occupation, "
            "MaritalStatus, Address "
            "FROM MfMember WHERE MemberId = ?", (member_id,)
        )
        member = _row_to_dict(cursor, cursor.fetchone())
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

        # --------- Additional info (scoring fields)
        cursor.execute(
            "SELECT * FROM MfMemberAdditionalInfo WHERE MemberId = ?", (member_id,)
        )
        data['additional_info'] = _row_to_dict(cursor, cursor.fetchone()) or {}

        #--------- Business info
        cursor.execute(
            "SELECT * FROM MfMemberBusiness WHERE MemberId = ?", (member_id,)
        )
        data['business'] = _row_to_dict(cursor, cursor.fetchone()) or {}

        # --------- All loans (for cycle, overdue history)
        cursor.execute(
            "SELECT LoanId, Cycle, PrincipalAmount, InstallmentAmount, LoanStatus, "
            "DisburseDate, GroupId, EmployeeId, BranchId, PrincipalOutstanding, "
            "InterestOutstanding, TotalOutstanding "
            "FROM MfLoan WHERE MemberId = ? ORDER BY Cycle DESC", (member_id,)
        )
        loans = _rows_to_dicts(cursor, cursor.fetchall())
        data['loans'] = loans
        data['current_loan'] = loans[0] if loans else None
        data['loan_cycle'] = loans[0]['Cycle'] if loans else 0

        # --------- Overdue count for previous loan cycle
        if len(loans) >= 2:
            prev_loan_id = loans[1]['LoanId']
            cursor.execute(
                "SELECT COUNT(*) as overdue_count FROM MfLoanCollection "
                "WHERE LoanId = ? AND OverdueAmount > 0", (prev_loan_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['prev_overdue_count'] = row['overdue_count'] if row else 0
        elif len(loans) == 1:
            # First loan — check overdue on current
            cursor.execute(
                "SELECT COUNT(*) as overdue_count FROM MfLoanCollection "
                "WHERE LoanId = ? AND OverdueAmount > 0", (loans[0]['LoanId'],)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['prev_overdue_count'] = row['overdue_count'] if row else 0
        else:
            data['prev_overdue_count'] = 0

        # --------- Repayment history (current or most recent loan)
        if loans:
            latest_loan_id = loans[0]['LoanId']
            cursor.execute(
                "SELECT COUNT(*) as total_collections, "
                "SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END) as overdue_collections "
                "FROM MfLoanCollection WHERE LoanId = ?", (latest_loan_id,)
            )
            rep = _row_to_dict(cursor, cursor.fetchone())
            data['total_collections'] = rep['total_collections'] if rep else 0
            data['overdue_collections'] = rep['overdue_collections'] if rep else 0
        else:
            data['total_collections'] = 0
            data['overdue_collections'] = 0

        # --------- Guarantor info (current + previous)
        if loans:
            current_loan_id = loans[0]['LoanId']
            cursor.execute(
                "SELECT FullName, ContactNumber, GrantorType FROM MfLoanGrantor "
                "WHERE LoanId = ?", (current_loan_id,)
            )
            data['current_guarantor'] = _row_to_dict(cursor, cursor.fetchone())

            if len(loans) >= 2:
                prev_loan_id = loans[1]['LoanId']
                cursor.execute(
                    "SELECT FullName, ContactNumber, GrantorType FROM MfLoanGrantor "
                    "WHERE LoanId = ?", (prev_loan_id,)
                )
                data['prev_guarantor'] = _row_to_dict(cursor, cursor.fetchone())
            else:
                data['prev_guarantor'] = None
        else:
            data['current_guarantor'] = None
            data['prev_guarantor'] = None

        # --------- Group info & member count
        if group_id:
            cursor.execute(
                "SELECT GroupId, GroupName, EmployeeId, BranchId FROM MfGroup "
                "WHERE GroupId = ?", (group_id,)
            )
            data['group'] = _row_to_dict(cursor, cursor.fetchone())

            cursor.execute(
                "SELECT COUNT(*) as member_count FROM MfMember "
                "WHERE GroupId = ? AND MemberStatus = 'Active'", (group_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['group_member_count'] = row['member_count'] if row else 0
        else:
            data['group'] = None
            data['group_member_count'] = 0

        # --------- Mobile number change (compare across loan cycles)
        data['mobile_changed'] = False
        if member.get('ContactNumber') and len(loans) >= 2:
            # We can't directly compare phone across cycles in MfMember (single row),
            # so we assume same if only 1 member record exists
            data['mobile_changed'] = False

        # --------- Branch info
        branch_id = loans[0]['BranchId'] if loans else (data['group'] or {}).get('BranchId')
        if branch_id:
            cursor.execute(
                "SELECT BranchId, BranchName, BranchCode, StartDate FROM AdBranch "
                "WHERE BranchId = ?", (branch_id,)
            )
            data['branch'] = _row_to_dict(cursor, cursor.fetchone())
        else:
            data['branch'] = None
        data['branch_id'] = branch_id

        # --------- Employee / Loan Officer info
        employee_id = loans[0]['EmployeeId'] if loans else (data['group'] or {}).get('EmployeeId')
        if employee_id:
            cursor.execute(
                "SELECT EmployeeId, EmployeeName, DesignationId, BranchId "
                "FROM HrEmployee WHERE EmployeeId = ?", (employee_id,)
            )
            data['employee'] = _row_to_dict(cursor, cursor.fetchone())
        else:
            data['employee'] = None
        data['employee_id'] = employee_id

        # --------- Branch performance data
        if branch_id:
            # Total borrowers in this branch
            cursor.execute(
                "SELECT COUNT(DISTINCT m.MemberId) as total_borrowers "
                "FROM MfLoan l JOIN MfMember m ON l.MemberId = m.MemberId "
                "WHERE l.BranchId = ? AND l.LoanStatus = 1", (branch_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['branch_total_borrowers'] = row['total_borrowers'] if row else 0

            # PAR > 30 days for this branch
            cursor.execute(
                "SELECT COUNT(*) as overdue_loans FROM MfLoan "
                "WHERE BranchId = ? AND LoanStatus = 1 AND PrincipalOutstanding > 0",
                (branch_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['branch_total_active_loans'] = row['overdue_loans'] if row else 0

            # Overdue loans in branch (PAR proxy)
            cursor.execute(
                "SELECT COUNT(DISTINCT l.LoanId) as par_loans "
                "FROM MfLoan l "
                "JOIN MfLoanCollection lc ON l.LoanId = lc.LoanId "
                "WHERE l.BranchId = ? AND l.LoanStatus = 1 "
                "AND lc.OverdueAmount > 0 AND lc.IsNewOverdue = 1",
                (branch_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['branch_par_loans'] = row['par_loans'] if row else 0

            # Branch performance tracker (latest)
            cursor.execute(
                "SELECT TOP 1 * FROM MfPerformanceTrackerData "
                "WHERE BranchId = ? ORDER BY BusinessDate DESC", (branch_id,)
            )
            data['branch_performance'] = _row_to_dict(cursor, cursor.fetchone())
        else:
            data['branch_total_borrowers'] = 0
            data['branch_total_active_loans'] = 0
            data['branch_par_loans'] = 0
            data['branch_performance'] = None

        # --------- LO performance data
        if employee_id:
            # Groups per LO
            cursor.execute(
                "SELECT COUNT(*) as group_count FROM MfGroup "
                "WHERE EmployeeId = ? AND GroupStatus = 'Active'", (employee_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['lo_group_count'] = row['group_count'] if row else 0

            # Total members per LO
            cursor.execute(
                "SELECT COUNT(DISTINCT m.MemberId) as member_count "
                "FROM MfGroup g JOIN MfMember m ON g.GroupId = m.GroupId "
                "WHERE g.EmployeeId = ? AND g.GroupStatus = 'Active' AND m.MemberStatus = 'Active'",
                (employee_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['lo_total_members'] = row['member_count'] if row else 0

            # LO PAR
            cursor.execute(
                "SELECT COUNT(DISTINCT l.LoanId) as par_loans "
                "FROM MfLoan l "
                "JOIN MfLoanCollection lc ON l.LoanId = lc.LoanId "
                "WHERE l.EmployeeId = ? AND l.LoanStatus = 1 "
                "AND lc.OverdueAmount > 0 AND lc.IsNewOverdue = 1",
                (employee_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['lo_par_loans'] = row['par_loans'] if row else 0

            cursor.execute(
                "SELECT COUNT(*) as total_active FROM MfLoan "
                "WHERE EmployeeId = ? AND LoanStatus = 1", (employee_id,)
            )
            row = _row_to_dict(cursor, cursor.fetchone())
            data['lo_total_active_loans'] = row['total_active'] if row else 0

            # LO performance tracker
            cursor.execute(
                "SELECT TOP 1 * FROM MfPerformanceTrackerData "
                "WHERE Loid = ? ORDER BY BusinessDate DESC", (employee_id,)
            )
            data['lo_performance'] = _row_to_dict(cursor, cursor.fetchone())
        else:
            data['lo_group_count'] = 0
            data['lo_total_members'] = 0
            data['lo_par_loans'] = 0
            data['lo_total_active_loans'] = 0
            data['lo_performance'] = None

        return data

    finally:
        conn.close()
