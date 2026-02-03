"""
Performance calculation utilities
Handles group performance, top performers, and risk analysis
"""

from services.data_processor import data_processor


def calculate_group_performance():
    """Calculate performance metrics for all groups"""
    if data_processor.df_processed is None:
        return []
    
    df = data_processor.df_processed
    
    # Group by group name
    group_performance = df.groupby('groupName').agg({
        'client_performance_score': ['mean', 'count'],
        'OverdueCollectionCount': 'sum',
        'loanAmount': ['sum', 'mean'],
        'repayment_rate': 'mean'
    }).round(2)
    
    group_performance.columns = ['avg_score', 'member_count', 'total_overdue',
                                   'total_loan_amount', 'avg_loan_amount', 'avg_repayment_rate']
    
    group_performance = group_performance.reset_index()
    
    # Convert to list of dicts
    result = []
    for _, row in group_performance.iterrows():
        result.append({
            'group_name': row['groupName'],
            'avg_score': float(row['avg_score']),
            'member_count': int(row['member_count']),
            'total_overdue': int(row['total_overdue']),
            'total_loan_amount': float(row['total_loan_amount']),
            'avg_loan_amount': float(row['avg_loan_amount']),
            'avg_repayment_rate': float(row['avg_repayment_rate'])
        })
    
    return result


def get_top_performers(limit=10, performance_type='clients'):
    """
    Get top performing clients or groups
    
    Args:
        limit: Number of top performers to return
        performance_type: 'clients' or 'groups'
    """
    if data_processor.df_processed is None:
        return []
    
    df = data_processor.df_processed
    
    if performance_type == 'clients':
        # Get unique clients with best scores
        top_clients = df.sort_values('client_performance_score', ascending=False).drop_duplicates('clientName').head(limit)
        
        result = []
        for _, client in top_clients.iterrows():
            result.append({
                'name': client['clientName'],
                'score': float(client['client_performance_score']),
                'loan_amount': float(client.get('loanAmount', 0)),
                'group': client.get('groupName', 'N/A'),
                'overdue_count': int(client.get('OverdueCollectionCount', 0))
            })
        
        return result
    
    elif performance_type == 'groups':
        # Calculate group performance and get top
        groups = calculate_group_performance()
        groups_sorted = sorted(groups, key=lambda x: x['avg_score'], reverse=True)
        
        return groups_sorted[:limit]
    
    return []


def get_risk_analysis(overdue_threshold=5):
    """
    Analyze high-risk clients
    
    Args:
        overdue_threshold: Number of overdue collections to be considered high risk
    """
    if data_processor.df_processed is None:
        return {
            'high_risk_clients': [],
            'total_high_risk': 0,
            'total_at_risk_amount': 0
        }
    
    df = data_processor.df_processed
    
    # Find high-risk clients
    high_risk = df[df['OverdueCollectionCount'] > overdue_threshold]
    
    # Get unique clients
    high_risk_unique = high_risk.sort_values('OverdueCollectionCount', ascending=False).drop_duplicates('clientName')
    
    risk_clients = []
    for _, client in high_risk_unique.iterrows():
        risk_clients.append({
            'name': client['clientName'],
            'overdue_count': int(client['OverdueCollectionCount']),
            'loan_amount': float(client.get('loanAmount', 0)),
            'performance_score': float(client['client_performance_score']),
            'group': client.get('groupName', 'N/A'),
            'loan_officer': client.get('loName', 'N/A')
        })
    
    return {
        'high_risk_clients': risk_clients,
        'total_high_risk': len(risk_clients),
        'total_at_risk_amount': float(high_risk_unique['loanAmount'].sum()) if 'loanAmount' in high_risk_unique.columns else 0,
        'overdue_threshold': overdue_threshold
    }


def get_business_performance():
    """Analyze performance by business type"""
    if data_processor.df_processed is None:
        return []
    
    df = data_processor.df_processed
    
    if 'loanPurpose' not in df.columns:
        return []
    
    # Group by business type
    business_perf = df.groupby('loanPurpose').agg({
        'client_performance_score': 'mean',
        'clientName': 'count',
        'loanAmount': 'sum'
    }).reset_index()
    
    business_perf.columns = ['business_type', 'avg_score', 'client_count', 'total_loan_amount']
    
    # Sort by average score
    business_perf = business_perf.sort_values('avg_score', ascending=False)
    
    result = []
    for _, row in business_perf.iterrows():
        result.append({
            'business_type': row['business_type'],
            'avg_score': float(row['avg_score']),
            'client_count': int(row['client_count']),
            'total_loan_amount': float(row['total_loan_amount'])
        })
    
    return result


def get_quick_insights():
    """Generate quick insights about the portfolio"""
    if data_processor.df_processed is None:
        return None
    
    insights = {
        'top_clients': get_top_performers(5, 'clients'),
        'top_groups': get_top_performers(5, 'groups'),
        'risk_analysis': get_risk_analysis(),
        'top_business_types': get_business_performance()[:5],
        'basic_stats': data_processor.get_basic_stats()
    }
    
    return insights
