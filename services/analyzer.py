"""
Analysis service combining data processing with AI analysis
"""

from services.data_processor import data_processor
from models.llama_handler import llama_handler


def create_client_context(client_data):
    """Create context string for client analysis"""
    context = f"""
CLIENT ANALYSIS REPORT:
Name: {client_data.get('clientName', 'N/A')}
Loan Amount: {client_data.get('loanAmount', 0):,} UGX
Loan Cycle: {client_data.get('cycle', 'N/A')}
Business: {client_data.get('loanPurpose', 'N/A')}
Performance Score: {client_data.get('client_performance_score', 0)}/100
Overdue Collections: {client_data.get('OverdueCollectionCount', 0)}
Repayment Rate: {client_data.get('repayment_rate', 0)*100:.1f}%
Group: {client_data.get('groupName', 'N/A')}
Loan Officer: {client_data.get('loName', 'N/A')}
Disbursement Date: {client_data.get('disbursementDate', 'N/A')}
"""
    return context


def create_group_context(group_name, group_data, member_details):
    """Create context string for group analysis"""
    context = f"""
GROUP ANALYSIS REPORT:
Group Name: {group_name}
Total Members: {group_data.get('member_count', 0)}
Total Loan Portfolio: {group_data.get('total_loan_amount', 0):,} UGX
Average Member Score: {group_data.get('avg_score', 0)}/100
Total Overdue Collections: {group_data.get('total_overdue', 0)}
Average Repayment Rate: {group_data.get('avg_repayment_rate', 0)*100:.1f}%

Member Performance Overview:
{member_details}
"""
    return context


def analyze_client(client_name):
    """
    Analyze a specific client
    
    Args:
        client_name: Name of the client to analyze
    
    Returns:
        Dictionary with client info and AI analysis
    """
    # Find client
    client_data = data_processor.find_client(client_name)
    
    if not client_data:
        return {
            'success': False,
            'error': 'Client not found',
            'suggestions': data_processor.get_all_clients(limit=5)
        }
    
    # Create context
    context = create_client_context(client_data)
    
    # Get AI analysis
    prompt = "Analyze this client's performance and provide recommendations in a friendly, conversational tone"
    ai_analysis = llama_handler.analyze_with_ai(prompt, context)
    
    # Prepare response
    result = {
        'success': True,
        'client_info': {
            'name': client_data.get('clientName', 'N/A'),
            'loan_amount': float(client_data.get('loanAmount', 0)),
            'business': client_data.get('loanPurpose', 'N/A'),
            'performance_score': float(client_data.get('client_performance_score', 0)),
            'overdue_count': int(client_data.get('OverdueCollectionCount', 0)),
            'repayment_rate': float(client_data.get('repayment_rate', 0)) * 100,
            'group': client_data.get('groupName', 'N/A'),
            'loan_officer': client_data.get('loName', 'N/A'),
            'disbursement_date': str(client_data.get('disbursementDate', 'N/A'))
        },
        'ai_analysis': ai_analysis,
        'risk_level': _calculate_risk_level(client_data)
    }
    
    return result


def analyze_group(group_name):
    """
    Analyze a specific group
    
    Args:
        group_name: Name of the group to analyze
    
    Returns:
        Dictionary with group info and AI analysis
    """
    # Find group
    group_data = data_processor.find_group(group_name)
    
    if not group_data:
        return {
            'success': False,
            'error': 'Group not found',
            'suggestions': data_processor.get_all_groups(limit=5)
        }
    
    # Get top members
    top_members = data_processor.get_group_members(group_name, top_n=5)
    
    # Create member details string
    member_details = "Top Performers:\n"
    for member in top_members:
        member_details += f"- {member['name']}: Score {member['score']}, Loan: {member['loan_amount']:,} UGX\n"
    
    # Create context
    context = create_group_context(group_data['groupName'], group_data, member_details)
    
    # Get AI analysis
    prompt = "Analyze this group's overall performance and provide friendly recommendations for improvement"
    ai_analysis = llama_handler.analyze_with_ai(prompt, context)
    
    # Prepare response
    result = {
        'success': True,
        'group_info': {
            'name': group_data['groupName'],
            'member_count': group_data['member_count'],
            'avg_score': group_data['avg_score'],
            'total_overdue': group_data['total_overdue'],
            'total_loan_amount': group_data['total_loan_amount'],
            'avg_loan_amount': group_data['avg_loan_amount'],
            'avg_repayment_rate': group_data['avg_repayment_rate'] * 100
        },
        'top_members': top_members,
        'ai_analysis': ai_analysis,
        'group_risk_level': _calculate_group_risk_level(group_data)
    }
    
    return result


def _calculate_risk_level(client_data):
    """Calculate risk level for a client"""
    score = client_data.get('client_performance_score', 0)
    overdue = client_data.get('OverdueCollectionCount', 0)
    
    if overdue > 5 or score < 40:
        return 'high'
    elif overdue > 2 or score < 60:
        return 'medium'
    else:
        return 'low'


def _calculate_group_risk_level(group_data):
    """Calculate risk level for a group"""
    avg_score = group_data.get('avg_score', 0)
    total_overdue = group_data.get('total_overdue', 0)
    member_count = group_data.get('member_count', 1)
    
    avg_overdue_per_member = total_overdue / member_count
    
    if avg_overdue_per_member > 3 or avg_score < 50:
        return 'high'
    elif avg_overdue_per_member > 1 or avg_score < 70:
        return 'medium'
    else:
        return 'low'
