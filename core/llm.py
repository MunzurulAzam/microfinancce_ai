from core.cloud import generate


class LlamaHandler:
    """Compatibility facade for existing portfolio and assistant callers."""
    def analyze_with_ai(self, prompt, context):
        result = generate(f"Use only these supplied facts; do not invent numbers.\nDATA: {context}\nQuestion: {prompt}", task='text')
        return result['text'] if result['success'] else self._fallback_analysis(prompt, context)

    def get_intent_ai(self, question):
        allowed = ['stats', 'insights', 'top_clients', 'top_groups', 'risk_analysis', 'analyze_client', 'analyze_group', 'business_performance']
        result = generate(f"Return only one intent from {allowed}, or general. Question: {question}", num_predict=40)
        intent = (result.get('text') or '').lower()
        return intent if intent in allowed else None

    def _fallback_analysis(self, prompt, context):
        
        if "CLIENT ANALYSIS" in context:
            return self._fallback_client_analysis(context)
        elif "GROUP ANALYSIS" in context:
            return self._fallback_group_analysis(context)
        else:
            return "Analysis data processed successfully. Key metrics available in the response."
    
    def _fallback_client_analysis(self, context):
        analysis = []
        
        if "Performance Score:" in context:
            score_line = [line for line in context.split('\n') if 'Performance Score:' in line][0]
            score = int(score_line.split(':')[1].strip().split('/')[0])
            
            if score >= 80:
                analysis.append("✅ EXCELLENT PERFORMANCE: This client shows outstanding performance with a high score.")
                analysis.append("Strengths: Consistent repayments, low risk, good business track record.")
                analysis.append("Recommendation: Consider for loan amount increase and priority service.")
            elif score >= 60:
                analysis.append("👍 GOOD PERFORMANCE: This client is performing well overall.")
                analysis.append("Strengths: Regular repayment behavior, stable business operations.")
                analysis.append("Recommendation: Maintain current support, monitor for improvement opportunities.")
            else:
                analysis.append("⚠️ NEEDS ATTENTION: This client requires closer monitoring.")
                analysis.append("Concerns: Performance indicators suggest some challenges.")
                analysis.append("Recommendation: Regular follow-ups, consider financial counseling or business support.")
        
        if "Overdue Collections:" in context:
            overdue_line = [line for line in context.split('\n') if 'Overdue Collections:' in line][0]
            overdue = int(overdue_line.split(':')[1].strip())
            
            if overdue > 5:
                analysis.append(f"\n⚠️ HIGH RISK: {overdue} overdue collections detected.")
                analysis.append("Action Required: Immediate follow-up and collection efforts needed.")
            elif overdue > 0:
                analysis.append(f"\n📊 {overdue} overdue collection(s) noted.")
                analysis.append("Action: Regular monitoring and gentle reminders recommended.")
        
        if "Repayment Rate:" in context:
            repay_line = [line for line in context.split('\n') if 'Repayment Rate:' in line][0]
            repay_rate = float(repay_line.split(':')[1].strip().replace('%', ''))
            
            if repay_rate >= 100:
                analysis.append(f"\n💰 EXCELLENT REPAYMENT: {repay_rate}% - Client is meeting or exceeding payment obligations.")
            elif repay_rate >= 80:
                analysis.append(f"\n💸 GOOD REPAYMENT: {repay_rate}% - Client is making regular payments.")
            else:
                analysis.append(f"\n⚠️ PAYMENT CONCERNS: {repay_rate}% - Below target repayment rate.")
        
        return "\n".join(analysis)
    
    def _fallback_group_analysis(self, context):
        analysis = []
        
        if "Average Member Score:" in context:
            score_line = [line for line in context.split('\n') if 'Average Member Score:' in line][0]
            avg_score = int(score_line.split(':')[1].strip().split('/')[0])
            
            if avg_score >= 80:
                analysis.append("🌟 EXCELLENT GROUP: This group shows outstanding collective performance.")
                analysis.append("Strengths: Strong peer support, good group dynamics, reliable members.")
                analysis.append("Recommendation: Use as model group, consider for group incentives.")
            elif avg_score >= 60:
                analysis.append("✅ PERFORMING WELL: This group maintains good standards.")
                analysis.append("Strengths: Stable membership, regular group meetings, mutual accountability.")
                analysis.append("Recommendation: Continue current practices, identify growth opportunities.")
            else:
                analysis.append("📉 NEEDS SUPPORT: This group requires attention and support.")
                analysis.append("Concerns: Performance indicators suggest coordination challenges.")
                analysis.append("Recommendation: Increase group meetings, provide training, strengthen leadership.")
        
        if "Total Members:" in context:
            members_line = [line for line in context.split('\n') if 'Total Members:' in line][0]
            members = int(members_line.split(':')[1].strip())
            
            if members < 5:
                analysis.append(f"\n👥 SMALL GROUP: {members} members - Consider recruitment for better risk distribution.")
            elif members > 20:
                analysis.append(f"\n👥 LARGE GROUP: {members} members - Ensure effective coordination and communication.")
        
        if "Total Overdue Collections:" in context:
            overdue_line = [line for line in context.split('\n') if 'Total Overdue Collections:' in line][0]
            total_overdue = int(overdue_line.split(':')[1].strip())
            
            if total_overdue > 10:
                analysis.append(f"\n⚠️ HIGH GROUP RISK: {total_overdue} total overdue collections.")
                analysis.append("Action: Group intervention needed, review solidarity mechanisms.")
            elif total_overdue > 0:
                analysis.append(f"\n📊 {total_overdue} overdue collections in group.")
                analysis.append("Action: Address through group meetings and peer support.")
        
        return "\n".join(analysis)


llama_handler = LlamaHandler()
