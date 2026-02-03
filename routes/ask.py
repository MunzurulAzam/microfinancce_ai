"""
Conversational Ask endpoint
Intelligent question answering system
"""

from flask import Blueprint, request, jsonify
from services.data_processor import data_processor
from services.analyzer import analyze_client, analyze_group
from services.performance import (
    get_top_performers,
    get_risk_analysis,
    get_quick_insights,
    get_business_performance
)
import re

ask_bp = Blueprint('ask', __name__)


def parse_question(question):
    """
    Parse user question and determine intent
    Returns: (intent, entity)
    """
    question_lower = question.lower().strip()
    
    # 1. Direct Keyword Matching (Fast)
    
    # Stats intent
    if any(k in question_lower for k in ['stats', 'statistics', 'overview', 'summary', 'total', 'how many']):
        return ('stats', None)
    
    # Insights intent
    if any(k in question_lower for k in ['insight', 'dashboard', 'overall performance', 'how are we doing']):
        return ('insights', None)
    
    # Top performers intent
    if any(k in question_lower for k in ['top', 'best', 'highest', 'performing', 'winner']):
        if 'group' in question_lower:
            return ('top_groups', None)
        return ('top_clients', None)
    
    # Risk patterns
    if any(k in question_lower for k in ['risk', 'overdue', 'problem', 'issue', 'default', 'high risk', 'danger']):
        return ('risk_analysis', None)
    
    # Business patterns
    if any(k in question_lower for k in ['business', 'sector', 'industry', 'loan purpose']):
        return ('business_performance', None)

    # 2. Regex for Entities (Client/Group)
    
    # Group analysis patterns
    group_patterns = [
        r'group\s+(.+)',
        r'about\s+group\s+(.+)',
        r'analyze\s+group\s+(.+)',
    ]
    for p in group_patterns:
        match = re.search(p, question_lower)
        if match: return ('analyze_group', match.group(1).strip())

    # Client analysis patterns
    client_patterns = [
        r'client\s+(.+)',
        r'customer\s+(.+)',
        r'analyze\s+(.+)',
        r'about\s+(.+)',
        r'how is\s+(.+)',
    ]
    for p in client_patterns:
        match = re.search(p, question_lower)
        if match:
            name = match.group(1).strip()
            # Clean name from stop words
            name = re.sub(r'(\?|\.|\!|doing|performing|is|the)$', '', name).strip()
            if name and len(name) > 2:
                return ('analyze_client', name)

    # 3. AI Fallback (If rules fail)
    return ('general', None)


def get_answer(intent, entity, question):
    """
    Get answer based on intent and entity
    """
    try:
        if intent == 'analyze_client':
            if not entity:
                return {
                    'success': False,
                    'answer': 'Please provide the client name. Example: "Analyze client John Doe"'
                }
            
            result = analyze_client(entity)
            
            if not result['success']:
                # Suggest similar clients
                clients = data_processor.get_all_clients(limit=5, search=entity[:3])
                suggestions = [c['name'] for c in clients]
                
                return {
                    'success': False,
                    'answer': f'Client "{entity}" not found.',
                    'suggestions': suggestions
                }
            
            # Format response
            client = result['client_info']
            answer = f"""
📊 **Analysis for {client['name']}:**

**Performance Score:** {client['performance_score']}/100
**Loan Amount:** {client['loan_amount']:,.0f} UGX
**Business:** {client['business']}
**Repayment Rate:** {client['repayment_rate']:.1f}%
**Overdue Count:** {client['overdue_count']}
**Risk Level:** {result['risk_level'].upper()}

**AI Analysis:**
{result['ai_analysis']}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': result
            }
        
        elif intent == 'analyze_group':
            if not entity:
                return {
                    'success': False,
                    'answer': 'Please provide the group name. Example: "Analyze group Team A"'
                }
            
            result = analyze_group(entity)
            
            if not result['success']:
                # Suggest similar groups
                groups = data_processor.get_all_groups(limit=5, search=entity[:3])
                suggestions = [g['name'] for g in groups]
                
                return {
                    'success': False,
                    'answer': f'Group "{entity}" not found.',
                    'suggestions': suggestions
                }
            
            # Format response
            group = result['group_info']
            members_list = '\n'.join([f"  - {m['name']}: {m['score']}/100" 
                                     for m in result['top_members'][:3]])
            
            answer = f"""
👥 **Analysis for {group['name']}:**

**Members:** {group['member_count']}
**Average Score:** {group['avg_score']:.1f}/100
**Total Loans:** {group['total_loan_amount']:,.0f} UGX
**Overdue Count:** {group['total_overdue']}
**Risk Level:** {result['group_risk_level'].upper()}

**Top Performers:**
{members_list}

**AI Analysis:**
{result['ai_analysis']}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': result
            }
        
        elif intent == 'stats':
            stats = data_processor.get_basic_stats()
            
            if not stats:
                return {
                    'success': False,
                    'answer': 'No data loaded. Please upload a CSV file first.'
                }
            
            answer = f"""
📈 **Portfolio Statistics:**

**Total Clients:** {stats['total_clients']}
**Total Groups:** {stats['total_groups']}
**Total Loan Officers:** {stats['total_loan_officers']}
**Total Loans:** {stats['total_loans']}
**Total Portfolio:** {stats['total_loan_portfolio']:,.0f} UGX
**Average Loan:** {stats['average_loan_amount']:,.0f} UGX
**Average Client Score:** {stats['average_client_score']:.1f}/100
**Clients with Overdue:** {stats['clients_with_overdue']}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': stats
            }
        
        elif intent == 'insights':
            insights = get_quick_insights()
            
            if not insights:
                return {
                    'success': False,
                    'answer': 'No data loaded yet.'
                }
            
            top_clients = '\n'.join([f"  {i+1}. {c['name']}: {c['score']}/100" 
                                    for i, c in enumerate(insights['top_clients'][:5])])
            
            risk = insights['risk_analysis']
            
            answer = f"""
💡 **Quick Insights:**

**🏆 Top 5 Clients:**
{top_clients}

**⚠️ Risk Status:**
  - High Risk Clients: {risk['total_high_risk']}
  - At Risk Amount: {risk['total_at_risk_amount']:,.0f} UGX

**📊 Portfolio Health:**
  - Average Score: {insights['basic_stats']['average_client_score']:.1f}/100
  - Total Portfolio: {insights['basic_stats']['total_loan_portfolio']:,.0f} UGX
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': insights
            }
        
        elif intent == 'top_clients':
            top_clients = get_top_performers(limit=10, performance_type='clients')
            
            clients_list = '\n'.join([f"  {i+1}. {c['name']}: {c['score']}/100 (Loan: {c['loan_amount']:,.0f} UGX)" 
                                     for i, c in enumerate(top_clients)])
            
            answer = f"""
🏆 **Top 10 Performing Clients:**

{clients_list}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': top_clients
            }
        
        elif intent == 'top_groups':
            top_groups = get_top_performers(limit=10, performance_type='groups')
            
            groups_list = '\n'.join([f"  {i+1}. {g['group_name']}: {g['avg_score']:.1f}/100 ({g['member_count']} members)" 
                                    for i, g in enumerate(top_groups)])
            
            answer = f"""
🏆 **Top 10 Performing Groups:**

{groups_list}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': top_groups
            }
        
        elif intent == 'risk_analysis':
            risk = get_risk_analysis(overdue_threshold=3)
            
            if risk['total_high_risk'] == 0:
                answer = "✅ No high-risk clients detected!"
            else:
                risk_list = '\n'.join([f"  - {c['name']}: {c['overdue_count']} overdue (Amount: {c['loan_amount']:,.0f} UGX)" 
                                      for c in risk['high_risk_clients'][:10]])
                
                answer = f"""
⚠️ **Risk Analysis:**

**Total High-Risk Clients:** {risk['total_high_risk']}
**Total At-Risk Amount:** {risk['total_at_risk_amount']:,.0f} UGX

**High-Risk Clients (Top 10):**
{risk_list}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': risk
            }
        
        elif intent == 'business_performance':
            business = get_business_performance()
            
            business_list = '\n'.join([f"  {i+1}. {b['business_type']}: {b['avg_score']:.1f}/100 ({b['client_count']} clients)" 
                                      for i, b in enumerate(business[:10])])
            
            answer = f"""
💼 **Business Performance Analysis:**

{business_list}
"""
            
            return {
                'success': True,
                'answer': answer.strip(),
                'data': business
            }
        
        else:
            # General response
            return {
                'success': True,
                'answer': """
I can help you with the following:

📊 **View Statistics:** "Show stats" or "Total clients"
👤 **Analyze Client:** "Analyze client [name]"
👥 **Analyze Group:** "Analyze group [name]"  
💡 **Quick Insights:** "Show insights"
🏆 **Top Performers:** "Show top clients" or "Show top groups"
⚠️ **Risk Analysis:** "Show risk analysis"
💼 **Business Performance:** "Business performance"

What would you like to know?
""".strip()
            }
    
    except Exception as e:
        return {
            'success': False,
            'answer': f'Error: {str(e)}'
        }


@ask_bp.route('/ask', methods=['POST'])
def ask_endpoint():
    """
    Single endpoint for all questions
    
    Request body: {"question": "Your question here"}
    Response: Natural language answer
    """
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'answer': 'Please provide the "question" field.',
                'example': {'question': 'Show me statistics'}
            }), 400
        
        question = data['question']
        
        # Parse question using rules first
        intent, entity = parse_question(question)
        
        # If rules return general, try AI intent classification
        if intent == 'general':
            from models.llama_handler import llama_handler
            ai_intent = llama_handler.get_intent_ai(question)
            if ai_intent:
                intent = ai_intent
        
        # Get answer
        response = get_answer(intent, entity, question)
        
        # Add metadata
        response['intent'] = intent
        if entity:
            response['entity'] = entity
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'answer': f'Error: {str(e)}'
        }), 500
