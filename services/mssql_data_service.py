"""
MSSQL Data Service
Replaces CSV-based data_processor for all portfolio-level features.
Uses the same credit scoring logic as the individual credit score endpoint.
"""

import pymssql
from datetime import datetime, date
from decimal import Decimal
from config import Config
from services.credit_scoring import calculate_credit_score


# ─── DB Connection ────────────────────────────────────────────────────────────

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
            print(f"[mssql_data_service] Available ODBC drivers: {available_drivers}")

            driver = None
            for d in ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server',
                      'SQL Server Native Client 11.0', 'SQL Server']:
                if d in available_drivers:
                    driver = f"{{{d}}}"
                    break

            if driver is None:
                raise RuntimeError(f"No SQL Server ODBC driver found. Install 'ODBC Driver 17 for SQL Server'. Available: {available_drivers}")

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

            print(f"[mssql_data_service] Connecting via pyodbc with driver: {driver}")
            conn = pyodbc.connect(full_conn_str, timeout=15)
            print("[mssql_data_service] pyodbc connection successful!")
            return conn

        except ImportError:
            if trusted:
                raise RuntimeError(
                    "pyodbc is not installed but Windows Auth (Trusted_Connection=True) requires it. "
                    "Run: pip install pyodbc"
                )
            print("[mssql_data_service] pyodbc not installed, falling back to pymssql (SQL Auth only)")
        except Exception as e:
            print(f"[mssql_data_service] pyodbc failed: {e}")
            if trusted:
                raise RuntimeError(
                    f"Windows Authentication requires pyodbc, but it failed: {e}. "
                    "Check that 'ODBC Driver 17 for SQL Server' is installed on this server."
                )

        # --- pymssql fallback (SQL Server Auth only, NOT Windows Auth) ---
        server = params.get('data source', params.get('server', ''))
        database = params.get('initial catalog', params.get('database', ''))

        port = 1433
        if server:
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


def _exec_query(query, params=None):
    """Internal helper to handle cursor/connection for both driver types."""
    conn = _get_connection()
    try:
        # Check if it's a pyodbc connection
        is_pyodbc = hasattr(conn, 'getinfo')
        cursor = conn.cursor()

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if is_pyodbc:
            # Convert pyodbc Row objects to dictionaries
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            # pymssql is already configured with as_dict=True
            return cursor.fetchall()
    finally:
        conn.close()


def _to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ─── Fetch light member list for bulk scoring ─────────────────────────────────

def _fetch_active_members(limit=200):
    """
    Fetch active members with their latest loan info in one query.
    Returns a list of dicts with just enough fields for lightweight scoring.
    """
    query = f"""
        SELECT TOP {limit}
            m.MemberId,
            m.FirstName,
            m.LastName,
            m.MemberCode,
            m.GroupId,
            m.MemberStatus,
            m.DateOfBirth,
            m.IdNumber,
            m.Gender,
            m.ContactNumber,

            -- Latest loan
            l.LoanId,
            l.Cycle        AS LoanCycle,
            l.PrincipalAmount,
            l.LoanStatus,
            l.BranchId,
            l.EmployeeId,
            l.PrincipalOutstanding,

            -- Group name
            g.GroupName,

            -- Branch name
            b.BranchName,

            -- LO name
            e.EmployeeName AS LOName
        FROM MfMember m
        LEFT JOIN (
            SELECT MemberId, MAX(Cycle) AS MaxCycle
            FROM MfLoan
            GROUP BY MemberId
        ) latest ON m.MemberId = latest.MemberId
        LEFT JOIN MfLoan l
            ON l.MemberId = m.MemberId AND l.Cycle = latest.MaxCycle
        LEFT JOIN MfGroup g ON m.GroupId = g.GroupId
        LEFT JOIN AdBranch b ON l.BranchId = b.BranchId
        LEFT JOIN HrEmployee e ON l.EmployeeId = e.EmployeeId
        WHERE m.MemberStatus = 'Active'
        ORDER BY m.MemberId
    """
    return _exec_query(query)


def _fetch_collection_summary(member_id, loan_id):
    """
    Fetch repayment summary for one loan (total + overdue collections).
    """
    if not loan_id:
        return 0, 0

    query = (
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END) AS overdue "
        "FROM MfLoanCollection WHERE LoanId = ?"
    )
    rows = _exec_query(query, (loan_id,))
    if rows:
        row = rows[0]
        return int(row['total'] or 0), int(row['overdue'] or 0)
    return 0, 0


def _fetch_prev_overdue(member_id, prev_loan_id):
    """Overdue count from previous loan cycle."""
    if not prev_loan_id:
        return 0
    query = (
        "SELECT COUNT(*) AS cnt FROM MfLoanCollection "
        "WHERE LoanId = ? AND OverdueAmount > 0"
    )
    rows = _exec_query(query, (prev_loan_id,))
    return int(rows[0]['cnt'] or 0) if rows else 0


def _build_scoring_data(row):
    """
    Build the 'data' dict that calculate_credit_score() expects,
    using only the fields available from the bulk query (fast path).
    """
    dob = row.get('DateOfBirth')
    age = None
    if dob:
        if isinstance(dob, datetime):
            dob = dob.date()
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    loan_id = row.get('LoanId')
    total_col, overdue_col = _fetch_collection_summary(row['MemberId'], loan_id)

    return {
        'member': {
            'MemberId':      row.get('MemberId'),
            'FirstName':     row.get('FirstName', ''),
            'LastName':      row.get('LastName', ''),
            'MemberCode':    row.get('MemberCode', ''),
            'ContactNumber': row.get('ContactNumber', ''),
            'MemberStatus':  row.get('MemberStatus', ''),
            'DateOfBirth':   row.get('DateOfBirth'),
            'IdNumber':      row.get('IdNumber', ''),
            'GroupId':       row.get('GroupId'),
            'Gender':        row.get('Gender', ''),
        },
        'age': age,
        'loan_cycle':          int(row.get('LoanCycle') or 0),
        'current_loan': {
            'LoanId':         loan_id,
            'PrincipalAmount': _to_float(row.get('PrincipalAmount')),
            'LoanStatus':      row.get('LoanStatus'),
            'BranchId':        row.get('BranchId'),
            'EmployeeId':      row.get('EmployeeId'),
        } if loan_id else None,
        'loans':               [{'LoanId': loan_id, 'Cycle': row.get('LoanCycle')}] if loan_id else [],
        'prev_overdue_count':  0,
        'total_collections':   total_col,
        'overdue_collections': overdue_col,
        'group_member_count':  0,
        'mobile_changed':      False,
        'additional_info':     {},
        'business':            {},
        'current_guarantor':   None,
        'prev_guarantor':      None,
        'branch':              {'BranchName': row.get('BranchName', 'N/A')},
        'branch_id':           row.get('BranchId'),
        'employee':            {'EmployeeName': row.get('LOName', 'N/A')},
        'employee_id':         row.get('EmployeeId'),
        'branch_total_borrowers':  0,
        'branch_total_active_loans': 0,
        'branch_par_loans':        0,
        'branch_performance':      None,
        'lo_group_count':          0,
        'lo_total_members':        0,
        'lo_par_loans':            0,
        'lo_total_active_loans':   0,
        'lo_performance':          None,
    }


# ─── Public API ──────────────────────────────────────────────────────────────

def get_basic_stats():
    """Portfolio-level statistics from MSSQL."""
    try:
        total_clients = _exec_query("SELECT COUNT(*) AS cnt FROM MfMember WHERE MemberStatus = 'Active'")[0]['cnt']
        total_groups = _exec_query("SELECT COUNT(*) AS cnt FROM MfGroup WHERE GroupStatus = 'Active'")[0]['cnt']
        total_loan_officers = _exec_query("SELECT COUNT(DISTINCT EmployeeId) AS cnt FROM MfLoan WHERE LoanStatus = 1")[0]['cnt']

        loan_row = _exec_query(
            "SELECT COUNT(*) AS cnt, "
            "ISNULL(SUM(PrincipalAmount), 0) AS portfolio, "
            "ISNULL(AVG(PrincipalAmount), 0) AS avg_loan "
            "FROM MfLoan WHERE LoanStatus = 1"
        )[0]

        total_loans      = int(loan_row['cnt'])
        total_portfolio  = _to_float(loan_row['portfolio'])
        average_loan     = _to_float(loan_row['avg_loan'])

        clients_with_overdue = _exec_query(
            "SELECT COUNT(DISTINCT l.MemberId) AS cnt "
            "FROM MfLoan l "
            "JOIN MfLoanCollection lc ON l.LoanId = lc.LoanId "
            "WHERE lc.OverdueAmount > 0"
        )[0]['cnt']

        return {
            'total_clients':        total_clients,
            'total_groups':         total_groups,
            'total_loan_officers':  total_loan_officers,
            'total_loans':          total_loans,
            'total_loan_portfolio': total_portfolio,
            'average_loan_amount':  average_loan,
            'average_client_score': 0,
            'clients_with_overdue': clients_with_overdue,
        }
    except Exception as e:
        print(f"[mssql_data_service] get_basic_stats error: {e}")
        return None


def get_all_clients(limit=100, offset=0, search=None):
    """Return paginated client list from MSSQL."""
    try:
        if search:
            query = (
                "SELECT m.MemberId, m.FirstName, m.LastName, m.MemberCode, "
                "m.MemberStatus, g.GroupName, e.EmployeeName AS loName "
                "FROM MfMember m "
                "LEFT JOIN MfGroup g ON m.GroupId = g.GroupId "
                "LEFT JOIN (SELECT MemberId, MAX(EmployeeId) AS EmployeeId FROM MfLoan GROUP BY MemberId) latest ON m.MemberId = latest.MemberId "
                "LEFT JOIN HrEmployee e ON latest.EmployeeId = e.EmployeeId "
                "WHERE m.MemberStatus = 'Active' "
                "AND (m.FirstName LIKE ? OR m.LastName LIKE ? OR m.MemberCode LIKE ?) "
                "ORDER BY m.FirstName "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
            )
            search_pattern = f'%{search}%'
            rows = _exec_query(query, (search_pattern, search_pattern, search_pattern, offset, limit))
        else:
            query = (
                "SELECT m.MemberId, m.FirstName, m.LastName, m.MemberCode, "
                "m.MemberStatus, g.GroupName, e.EmployeeName AS loName "
                "FROM MfMember m "
                "LEFT JOIN MfGroup g ON m.GroupId = g.GroupId "
                "LEFT JOIN (SELECT MemberId, MAX(EmployeeId) AS EmployeeId FROM MfLoan GROUP BY MemberId) latest ON m.MemberId = latest.MemberId "
                "LEFT JOIN HrEmployee e ON latest.EmployeeId = e.EmployeeId "
                "WHERE m.MemberStatus = 'Active' "
                "ORDER BY m.FirstName "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
            )
            rows = _exec_query(query, (offset, limit))

        return [
            {
                'name':   f"{r['FirstName']} {r['LastName']}".strip(),
                'code':   r.get('MemberCode', ''),
                'group':  r.get('GroupName', 'N/A'),
                'lo':     r.get('loName', 'N/A'),
                'status': r.get('MemberStatus', ''),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[mssql_data_service] get_all_clients error: {e}")
        return []


def get_all_groups(limit=100, offset=0, search=None):
    """Return paginated group list from MSSQL."""
    try:
        if search:
            query = (
                "SELECT g.GroupId, g.GroupName, g.GroupStatus, "
                "COUNT(m.MemberId) AS member_count, "
                "e.EmployeeName AS loName "
                "FROM MfGroup g "
                "LEFT JOIN MfMember m ON g.GroupId = m.GroupId AND m.MemberStatus = 'Active' "
                "LEFT JOIN HrEmployee e ON g.EmployeeId = e.EmployeeId "
                "WHERE g.GroupStatus = 'Active' "
                "AND g.GroupName LIKE ? "
                "GROUP BY g.GroupId, g.GroupName, g.GroupStatus, e.EmployeeName "
                "ORDER BY g.GroupName "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
            )
            rows = _exec_query(query, (f'%{search}%', offset, limit))
        else:
            query = (
                "SELECT g.GroupId, g.GroupName, g.GroupStatus, "
                "COUNT(m.MemberId) AS member_count, "
                "e.EmployeeName AS loName "
                "FROM MfGroup g "
                "LEFT JOIN MfMember m ON g.GroupId = m.GroupId AND m.MemberStatus = 'Active' "
                "LEFT JOIN HrEmployee e ON g.EmployeeId = e.EmployeeId "
                "WHERE g.GroupStatus = 'Active' "
                "GROUP BY g.GroupId, g.GroupName, g.GroupStatus, e.EmployeeName "
                "ORDER BY g.GroupName "
                "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
            )
            rows = _exec_query(query, (offset, limit))

        return [
            {
                'name':         r.get('GroupName', ''),
                'member_count': int(r.get('member_count') or 0),
                'lo':           r.get('loName', 'N/A'),
                'status':       r.get('GroupStatus', ''),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[mssql_data_service] get_all_groups error: {e}")
        return []


def get_top_performers(limit=10, performance_type='clients'):
    """Score active members, then return top/bottom."""
    try:
        members = _fetch_active_members(limit=min(limit * 10, 300))
        scored = []
        for row in members:
            try:
                data = _build_scoring_data(row)
                result = calculate_credit_score(data)
                scored.append({
                    'member_id':   row['MemberId'],
                    'name':        f"{row.get('FirstName','')} {row.get('LastName','')}".strip(),
                    'code':        row.get('MemberCode', ''),
                    'score':       result['percentage'],
                    'classification': result['classification'],
                    'risk_level':  result['risk_level'],
                    'loan_amount': _to_float(row.get('PrincipalAmount')),
                    'group':       row.get('GroupName', 'N/A'),
                    'branch':      row.get('BranchName', 'N/A'),
                    'lo':          row.get('LOName', 'N/A'),
                })
            except Exception:
                continue

        if performance_type == 'clients':
            return sorted(scored, key=lambda x: x['score'], reverse=True)[:limit]
        elif performance_type == 'groups':
            group_map = {}
            for s in scored:
                g = s['group']
                if g not in group_map:
                    group_map[g] = {'scores': [], 'loan_total': 0, 'members': 0}
                group_map[g]['scores'].append(s['score'])
                group_map[g]['loan_total'] += s['loan_amount']
                group_map[g]['members'] += 1

            groups = []
            for gname, gdata in group_map.items():
                avg = sum(gdata['scores']) / len(gdata['scores']) if gdata['scores'] else 0
                groups.append({
                    'group_name':       gname,
                    'avg_score':        round(avg, 1),
                    'member_count':     gdata['members'],
                    'total_loan_amount': gdata['loan_total'],
                })
            return sorted(groups, key=lambda x: x['avg_score'], reverse=True)[:limit]
        return []
    except Exception as e:
        print(f"[mssql_data_service] get_top_performers error: {e}")
        return []


def get_risk_analysis(overdue_threshold=3):
    """Identify high-risk clients using credit score classification."""
    try:
        members = _fetch_active_members(limit=300)
        high_risk = []
        total_at_risk = 0.0
        for row in members:
            try:
                data = _build_scoring_data(row)
                result = calculate_credit_score(data)
                if result['percentage'] < 70:
                    loan_amount = _to_float(row.get('PrincipalAmount'))
                    high_risk.append({
                        'name':           f"{row.get('FirstName','')} {row.get('LastName','')}".strip(),
                        'code':           row.get('MemberCode', ''),
                        'score':          result['percentage'],
                        'classification': result['classification'],
                        'loan_amount':    loan_amount,
                        'overdue_count':  data['overdue_collections'],
                        'group':          row.get('GroupName', 'N/A'),
                        'branch':         row.get('BranchName', 'N/A'),
                        'lo':             row.get('LOName', 'N/A'),
                    })
                    total_at_risk += loan_amount
            except Exception: continue
        high_risk.sort(key=lambda x: x['score'])
        return {
            'high_risk_clients':   high_risk,
            'total_high_risk':     len(high_risk),
            'total_at_risk_amount': total_at_risk,
        }
    except Exception as e:
        print(f"[mssql_data_service] get_risk_analysis error: {e}")
        return {'high_risk_clients': [], 'total_high_risk': 0}


def get_quick_insights():
    """Generate quick portfolio insights."""
    try:
        return {
            'top_clients':      get_top_performers(5, 'clients'),
            'top_groups':       get_top_performers(5, 'groups'),
            'risk_analysis':    get_risk_analysis(),
            'basic_stats':      get_basic_stats(),
        }
    except Exception as e:
        print(f"[mssql_data_service] get_quick_insights error: {e}")
        return None
