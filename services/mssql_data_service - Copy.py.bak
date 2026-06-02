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
    return pymssql.connect(
        server=Config.MSSQL_SERVER,
        port=Config.MSSQL_PORT,
        user=Config.MSSQL_USER,
        password=Config.MSSQL_PASSWORD,
        database=Config.MSSQL_DATABASE,
        login_timeout=15,
        as_dict=True
    )


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
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
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
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def _fetch_collection_summary(member_id, loan_id):
    """
    Fetch repayment summary for one loan (total + overdue collections).
    """
    if not loan_id:
        return 0, 0
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN OverdueAmount > 0 THEN 1 ELSE 0 END) AS overdue "
            "FROM MfLoanCollection WHERE LoanId = %s",
            (loan_id,)
        )
        row = cursor.fetchone()
        if row:
            return int(row['total'] or 0), int(row['overdue'] or 0)
        return 0, 0
    finally:
        conn.close()


def _fetch_prev_overdue(member_id, prev_loan_id):
    """Overdue count from previous loan cycle."""
    if not prev_loan_id:
        return 0
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM MfLoanCollection "
            "WHERE LoanId = %s AND OverdueAmount > 0",
            (prev_loan_id,)
        )
        row = cursor.fetchone()
        return int(row['cnt'] or 0) if row else 0
    finally:
        conn.close()


def _build_scoring_data(row):
    """
    Build the 'data' dict that calculate_credit_score() expects,
    using only the fields available from the bulk query (fast path).
    Heavy fields (branch/LO performance) are skipped for bulk scoring —
    we only use client-level scoring for ranking purposes.
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
        'prev_overdue_count':  0,          # requires extra query; neutral for bulk
        'total_collections':   total_col,
        'overdue_collections': overdue_col,
        'group_member_count':  0,          # neutral for bulk
        'mobile_changed':      False,
        'additional_info':     {},         # MfMemberAdditionalInfo — neutral for bulk
        'business':            {},
        'current_guarantor':   None,
        'prev_guarantor':      None,
        'branch':              {'BranchName': row.get('BranchName', 'N/A')},
        'branch_id':           row.get('BranchId'),
        'employee':            {'EmployeeName': row.get('LOName', 'N/A')},
        'employee_id':         row.get('EmployeeId'),
        # Branch / LO performance (skip for bulk — use neutral values)
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
    """
    Portfolio-level statistics from MSSQL.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS cnt FROM MfMember WHERE MemberStatus = 'Active'")
        total_clients = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(*) AS cnt FROM MfGroup WHERE GroupStatus = 'Active'")
        total_groups = cursor.fetchone()['cnt']

        cursor.execute(
            "SELECT COUNT(DISTINCT EmployeeId) AS cnt FROM MfLoan WHERE LoanStatus = 1"
        )
        total_loan_officers = cursor.fetchone()['cnt']

        cursor.execute(
            "SELECT COUNT(*) AS cnt, "
            "ISNULL(SUM(PrincipalAmount), 0) AS portfolio, "
            "ISNULL(AVG(PrincipalAmount), 0) AS avg_loan "
            "FROM MfLoan WHERE LoanStatus = 1"
        )
        loan_row = cursor.fetchone()
        total_loans      = int(loan_row['cnt'])
        total_portfolio  = _to_float(loan_row['portfolio'])
        average_loan     = _to_float(loan_row['avg_loan'])

        # Clients with at least one overdue collection
        cursor.execute(
            "SELECT COUNT(DISTINCT l.MemberId) AS cnt "
            "FROM MfLoan l "
            "JOIN MfLoanCollection lc ON l.LoanId = lc.LoanId "
            "WHERE lc.OverdueAmount > 0"
        )
        clients_with_overdue = cursor.fetchone()['cnt']

        conn.close()

        return {
            'total_clients':        total_clients,
            'total_groups':         total_groups,
            'total_loan_officers':  total_loan_officers,
            'total_loans':          total_loans,
            'total_loan_portfolio': total_portfolio,
            'average_loan_amount':  average_loan,
            'average_client_score': 0,     # computed separately when needed
            'clients_with_overdue': clients_with_overdue,
        }
    except Exception as e:
        print(f"[mssql_data_service] get_basic_stats error: {e}")
        return None


def get_all_clients(limit=100, offset=0, search=None):
    """
    Return paginated client list from MSSQL.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        if search:
            cursor.execute(
                "SELECT m.MemberId, m.FirstName, m.LastName, m.MemberCode, "
                "m.MemberStatus, g.GroupName, e.EmployeeName AS loName "
                "FROM MfMember m "
                "LEFT JOIN MfGroup g ON m.GroupId = g.GroupId "
                "LEFT JOIN (SELECT MemberId, MAX(EmployeeId) AS EmployeeId FROM MfLoan GROUP BY MemberId) latest ON m.MemberId = latest.MemberId "
                "LEFT JOIN HrEmployee e ON latest.EmployeeId = e.EmployeeId "
                "WHERE m.MemberStatus = 'Active' "
                "AND (m.FirstName LIKE %s OR m.LastName LIKE %s OR m.MemberCode LIKE %s) "
                "ORDER BY m.FirstName "
                "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
                (f'%{search}%', f'%{search}%', f'%{search}%', offset, limit)
            )
        else:
            cursor.execute(
                "SELECT m.MemberId, m.FirstName, m.LastName, m.MemberCode, "
                "m.MemberStatus, g.GroupName, e.EmployeeName AS loName "
                "FROM MfMember m "
                "LEFT JOIN MfGroup g ON m.GroupId = g.GroupId "
                "LEFT JOIN (SELECT MemberId, MAX(EmployeeId) AS EmployeeId FROM MfLoan GROUP BY MemberId) latest ON m.MemberId = latest.MemberId "
                "LEFT JOIN HrEmployee e ON latest.EmployeeId = e.EmployeeId "
                "WHERE m.MemberStatus = 'Active' "
                "ORDER BY m.FirstName "
                "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
                (offset, limit)
            )

        rows = cursor.fetchall()
        conn.close()

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
    """
    Return paginated group list from MSSQL.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        base_sql = (
            "SELECT g.GroupId, g.GroupName, g.GroupStatus, "
            "COUNT(m.MemberId) AS member_count, "
            "e.EmployeeName AS loName "
            "FROM MfGroup g "
            "LEFT JOIN MfMember m ON g.GroupId = m.GroupId AND m.MemberStatus = 'Active' "
            "LEFT JOIN HrEmployee e ON g.EmployeeId = e.EmployeeId "
            "WHERE g.GroupStatus = 'Active' "
        )
        if search:
            base_sql += "AND g.GroupName LIKE %s "
            params = (f'%{search}%', offset, limit)
        else:
            params = (offset, limit)

        base_sql += (
            "GROUP BY g.GroupId, g.GroupName, g.GroupStatus, e.EmployeeName "
            "ORDER BY g.GroupName "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
        )

        cursor.execute(base_sql, params)
        rows = cursor.fetchall()
        conn.close()

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
    """
    Score active members using the same credit scoring logic, then return top/bottom.
    performance_type: 'clients' or 'groups'
    """
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
                    'overdue_count': 0,  # overdue_collections from collection summary
                })
            except Exception:
                continue

        if performance_type == 'clients':
            # Top = highest score
            top = sorted(scored, key=lambda x: x['score'], reverse=True)[:limit]
            return top

        elif performance_type == 'groups':
            # Aggregate by group name
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
    """
    Identify high-risk clients using credit score classification from MSSQL data.
    High risk = classification 'High Risk' OR 'Moderate Risk' (score < 70%).
    """
    try:
        members = _fetch_active_members(limit=300)

        high_risk = []
        total_at_risk = 0.0

        for row in members:
            try:
                data = _build_scoring_data(row)
                result = calculate_credit_score(data)

                # High risk = score below 70% (Moderate Risk or High Risk)
                if result['percentage'] < 70:
                    loan_amount = _to_float(row.get('PrincipalAmount'))
                    overdue_col = data['overdue_collections']

                    high_risk.append({
                        'name':           f"{row.get('FirstName','')} {row.get('LastName','')}".strip(),
                        'code':           row.get('MemberCode', ''),
                        'score':          result['percentage'],
                        'classification': result['classification'],
                        'loan_amount':    loan_amount,
                        'overdue_count':  overdue_col,
                        'group':          row.get('GroupName', 'N/A'),
                        'branch':         row.get('BranchName', 'N/A'),
                        'lo':             row.get('LOName', 'N/A'),
                    })
                    total_at_risk += loan_amount
            except Exception:
                continue

        # Sort by score ascending (worst first)
        high_risk.sort(key=lambda x: x['score'])

        return {
            'high_risk_clients':   high_risk,
            'total_high_risk':     len(high_risk),
            'total_at_risk_amount': total_at_risk,
            'overdue_threshold':   overdue_threshold,
        }
    except Exception as e:
        print(f"[mssql_data_service] get_risk_analysis error: {e}")
        return {
            'high_risk_clients':   [],
            'total_high_risk':     0,
            'total_at_risk_amount': 0,
        }


def get_quick_insights():
    """Generate quick portfolio insights from MSSQL."""
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
