from flask import Blueprint, request, jsonify
from portfolio.data_service import (
    get_basic_stats,
    get_all_clients,
    get_all_groups,
    get_top_performers,
    get_risk_analysis,
    get_quick_insights,
)
from portfolio.analyzer import analyze_client, analyze_group
from portfolio.performance import get_business_performance
from credit_scoring.member_repo import search_member, get_member_full_data
from credit_scoring.scoring import calculate_credit_score
from credit_scoring.ai_advisor import get_ai_analysis
import re

ask_bp = Blueprint('ask', __name__)


def parse_question(question):
    """Returns (intent, entity) for a user question."""
    question_lower = question.lower().strip()

    credit_patterns = [
        r'credit\s*scor(?:e|ing)\s+(?:for\s+)?(.+)',
        r'score\s+(?:for\s+)?(?:client\s+)?(.+)',
        r'scoring\s+(?:for\s+)?(.+)',
        r'check\s+(?:credit\s+)?score\s+(?:for\s+|of\s+)?(.+)',
        r'evaluate\s+credit\s+(?:for\s+)?(.+)',
        r'credit\s+(?:check|analysis|report)\s+(?:for\s+)?(.+)',
    ]
    for p in credit_patterns:
        match = re.search(p, question_lower)
        if match:
            entity = match.group(1).strip().rstrip('?.!')
            if entity and len(entity) > 1:
                return ('credit_score', entity)

    if any(k in question_lower for k in ['stats', 'statistics', 'overview', 'summary', 'total', 'how many']):
        return ('stats', None)

    if any(k in question_lower for k in ['insight', 'dashboard', 'overall performance', 'how are we doing']):
        return ('insights', None)

    if any(k in question_lower for k in ['top', 'best', 'highest', 'performing', 'winner']):
        if 'group' in question_lower:
            return ('top_groups', None)
        return ('top_clients', None)

    if any(k in question_lower for k in ['risk', 'overdue', 'problem', 'issue', 'default', 'high risk', 'danger']):
        return ('risk_analysis', None)

    if any(k in question_lower for k in ['business', 'sector', 'industry', 'loan purpose']):
        return ('business_performance', None)

    group_patterns = [
        r'group\s+(.+)',
        r'about\s+group\s+(.+)',
        r'analyze\s+group\s+(.+)',
    ]
    for p in group_patterns:
        match = re.search(p, question_lower)
        if match: return ('analyze_group', match.group(1).strip())

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
            name = re.sub(r'(\?|\.|\!|doing|performing|is|the)$', '', name).strip()
            if name and len(name) > 2:
                return ('analyze_client', name)

    return ('general', None)


def get_answer(intent, entity, question):
    try:
        if intent == 'credit_score':
            return _handle_credit_score(entity)

        elif intent == 'analyze_client':
            if not entity:
                return {
                    'success': False,
                    'answer': 'Please provide the client name. Example: "Analyze client John Doe"'
                }

            result = analyze_client(entity)

            if not result['success']:
                suggestions_list = get_all_clients(limit=5, search=entity[:3])
                suggestions = [c['name'] for c in suggestions_list]

                return {
                    'success': False,
                    'answer': f'Client "{entity}" not found.',
                    'suggestions': suggestions
                }

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
                suggestions_list = get_all_groups(limit=5, search=entity[:3])
                suggestions = [g['name'] for g in suggestions_list]

                return {
                    'success': False,
                    'answer': f'Group "{entity}" not found.',
                    'suggestions': suggestions
                }

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
            stats = get_basic_stats()

            if not stats:
                return {
                    'success': False,
                    'answer': 'Could not connect to database. Please check the connection.'
                }

            answer = f"""
📈 **Portfolio Statistics (Live from Database):**

**Total Clients:** {stats['total_clients']}
**Total Groups:** {stats['total_groups']}
**Total Loan Officers:** {stats['total_loan_officers']}
**Total Active Loans:** {stats['total_loans']}
**Total Portfolio:** {stats['total_loan_portfolio']:,.0f}
**Average Loan:** {stats['average_loan_amount']:,.0f}
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
                    'answer': 'Could not connect to database.'
                }

            top_clients = '\n'.join([f"  {i+1}. {c['name']}: {c['score']:.1f}% ({c['classification']})" 
                                    for i, c in enumerate(insights['top_clients'][:5])])

            risk = insights['risk_analysis']

            answer = f"""
💡 **Quick Insights (Live from Database):**

**🏆 Top 5 Clients by Credit Score:**
{top_clients}

**⚠️ Risk Status:**
  - High/Moderate Risk Clients: {risk['total_high_risk']}
  - At Risk Amount: {risk['total_at_risk_amount']:,.0f}

**📊 Portfolio:**
  - Total Clients: {insights['basic_stats']['total_clients']}
  - Total Portfolio: {insights['basic_stats']['total_loan_portfolio']:,.0f}
"""

            return {
                'success': True,
                'answer': answer.strip(),
                'data': insights
            }

        elif intent == 'top_clients':
            top_clients = get_top_performers(limit=10, performance_type='clients')

            clients_list = '\n'.join([f"  {i+1}. {c['name']}: {c['score']:.1f}% — {c['classification']} (Loan: {c['loan_amount']:,.0f})" 
                                     for i, c in enumerate(top_clients)])

            answer = f"""
🏆 **Top 10 Clients by Credit Score (from DB):**

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
                answer = "✅ No high-risk clients detected! All scored above 70%."
            else:
                risk_list = '\n'.join([f"  - {c['name']} ({c['code']}): {c['score']:.1f}% — {c['classification']} (Loan: {c['loan_amount']:,.0f})" 
                                      for c in risk['high_risk_clients'][:10]])

                answer = f"""
⚠️ **Risk Analysis (Credit Score Based):**

**Total High/Moderate Risk Clients:** {risk['total_high_risk']}
**Total At-Risk Amount:** {risk['total_at_risk_amount']:,.0f}

**Clients Scoring Below 70% (Top 10):**
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
            return {
                'success': True,
                'answer': """
I can help you with the following:

🎯 **Credit Score:** "Credit score for [name or ID]" ⭐ NEW
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


def _handle_credit_score(entity):
    """Fetch member data from MSSQL, score it, and attach the AI analysis."""
    if not entity:
        return {
            'success': False,
            'answer': 'Please provide a client name, ID, or member code.\n'
                      'Example: "Credit score for Nyakisiki Lydia" or "Score CLN0025881"'
        }

    try:
        members = search_member(entity)

        if not members:
            return {
                'success': False,
                'answer': f'❌ No client found matching "{entity}".\n'
                          f'Try using full name, Member ID, or Member Code (e.g. CLN0025881).'
            }

        member = members[0]
        member_id = member['MemberId']

        full_data = get_member_full_data(member_id)
        if not full_data:
            return {
                'success': False,
                'answer': f'❌ Could not fetch full data for member ID {member_id}.'
            }

        score_result = calculate_credit_score(full_data)

        ai_analysis = get_ai_analysis(score_result)
        score_result['ai_analysis'] = ai_analysis

        answer = _format_credit_score_text(score_result)

        if len(members) > 1:
            others = [f"{m['FirstName']} {m['LastName']} ({m['MemberCode']})" for m in members[1:5]]
            answer += f"\n\n📋 Other matches: {', '.join(others)}"

        return {
            'success': True,
            'answer': answer,
            'data': score_result,
            'credit_score': True
        }

    except Exception as e:
        return {
            'success': False,
            'answer': f'❌ Error calculating credit score: {str(e)}'
        }


def _format_credit_score_text(sr):
    cls_emoji = {
        'Excellent': '🟢',
        'Good': '🔵',
        'Moderate Risk': '🟡',
        'High Risk': '🔴'
    }
    emoji = cls_emoji.get(sr['classification'], '⚪')

    lines = [
        f"🎯 **Credit Score Report — {sr['member_name']}** ({sr['member_code']})",
        f"",
        f"{'═' * 40}",
        f"{emoji} **Overall: {sr['percentage']}% — {sr['classification']}**",
        f"Total Score: {sr['total_score']} / {sr['max_score']} (Client Scoring — 21 parameters)",
        f"{'═' * 40}",
        f"",
        f"📋 **Client Scoring:** {sr['client_scoring']['score']}/{sr['client_scoring']['max']} ({sr['client_scoring']['percentage']}%)",
    ]

    for d in sr['client_scoring']['details']:
        bar = '█' * d['score'] + '░' * (5 - d['score'])
        lines.append(f"  {bar} {d['score']}/5 — {d['parameter']}: {d['reason']}")

    lines.append(f"")
    lines.append(f"{'─' * 40}")
    lines.append(f"🤖 **AI Analysis:**")
    lines.append(sr.get('ai_analysis', 'No AI analysis available.'))

    return '\n'.join(lines)


@ask_bp.route('/ask', methods=['POST'])
def ask_endpoint():
    """POST /api/ask — {"question": str} in, natural-language answer out."""
    try:
        data = request.get_json()

        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'answer': 'Please provide the "question" field.',
                'example': {'question': 'Show me statistics'}
            }), 400

        question = data['question']

        intent, entity = parse_question(question)

        if intent == 'general':
            from core.llm import llama_handler
            ai_intent = llama_handler.get_intent_ai(question)
            if ai_intent:
                intent = ai_intent

        response = get_answer(intent, entity, question)

        response['intent'] = intent
        if entity:
            response['entity'] = entity

        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'answer': f'Error: {str(e)}'
        }), 500
