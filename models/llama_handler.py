"""
AI Model handler for Llama integration
Handles model loading, prompting, and fallback analysis
"""

import os
from config import Config


class LlamaHandler:
    """Manages Llama AI model for analysis"""
    
    def __init__(self):
        self.llm = None
        self.model_loaded = False
        
        if Config.USE_AI_MODEL:
            self._load_model()
    
    def _load_model(self):
        """Load Llama model if available"""
        try:
            # Check if model exists
            if not os.path.exists(Config.MODEL_PATH):
                print(f"⚠️  Model not found at {Config.MODEL_PATH}")
                print(f"📥 Please download the model from:")
                print(f"   {Config.MODEL_URL}")
                print(f"   Save it as: {Config.MODEL_PATH}")
                print("💡 API will use fallback analysis without AI model")
                self.model_loaded = False
                return
            
            from llama_cpp import Llama
            
            print("🔄 Loading Llama model...")
            self.llm = Llama(
                model_path=Config.MODEL_PATH,
                n_ctx=Config.MODEL_N_CTX,
                n_threads=Config.MODEL_N_THREADS,
                verbose=False
            )
            self.model_loaded = True
            print("✅ Llama model loaded successfully!")
            
        except ImportError:
            print("⚠️  llama-cpp-python not installed")
            print("💡 Install with: pip install llama-cpp-python")
            print("💡 API will use fallback analysis")
            self.model_loaded = False
        except Exception as e:
            print(f"⚠️  Error loading model: {e}")
            print("💡 API will use fallback analysis")
            self.model_loaded = False
    
    def analyze_with_ai(self, prompt, context):
        """
        Analyze using AI model or fallback to rule-based analysis
        """
        if self.model_loaded and self.llm:
            return self._ai_analysis(prompt, context)
        else:
            return self._fallback_analysis(prompt, context)
            
    def get_intent_ai(self, question):
        """Use AI to classify the user intent"""
        if not self.model_loaded or not self.llm:
            return None
            
        system_prompt = """
Classify the following microfinance question into one of these intents:
- stats: Overall portfolio balance, count of clients/groups
- insights: Highlights and quick summary
- top_clients: Best performing individual clients
- top_groups: Best performing groups
- risk_analysis: Problems, overdue, defaults, high risk
- analyze_client: Detailed info about a specific person
- analyze_group: Detailed info about a specific group
- business_performance: Performance by business type or sector
- general: Any other question or help

Respond ONLY with the intent name and nothing else.
Question: """
        
        try:
            response = self.llm(
                f"{system_prompt}{question}",
                max_tokens=10,
                temperature=0.1,
                echo=False
            )
            intent = response['choices'][0]['text'].strip().lower()
            return intent if intent in ['stats', 'insights', 'top_clients', 'top_groups', 'risk_analysis', 'analyze_client', 'analyze_group', 'business_performance'] else None
        except:
            return None
    
    def _ai_analysis(self, prompt, context):
        """Use Llama model for analysis"""
        full_prompt = f"""
You are a friendly microfinance analyst assistant. You're helping a loan officer understand their portfolio.

DATA:
{context}

QUESTION: {prompt}

Please provide a helpful, conversational analysis with:
- Key observations in simple terms
- What's working well
- Areas for improvement
- Specific, actionable recommendations
- Keep it friendly and encouraging

Answer in a natural, conversational tone:
"""
        
        try:
            response = self.llm(
                full_prompt,
                max_tokens=Config.MODEL_MAX_TOKENS,
                temperature=Config.MODEL_TEMPERATURE,
                echo=False
            )
            return response['choices'][0]['text'].strip()
        except Exception as e:
            print(f"AI analysis error: {e}")
            return self._fallback_analysis(prompt, context)
    
    def _fallback_analysis(self, prompt, context):
        """Rule-based analysis without AI model"""
        
        # Extract key info from context
        if "CLIENT ANALYSIS" in context:
            return self._fallback_client_analysis(context)
        elif "GROUP ANALYSIS" in context:
            return self._fallback_group_analysis(context)
        else:
            return "Analysis data processed successfully. Key metrics available in the response."
    
    def _fallback_client_analysis(self, context):
        """Generate client analysis without AI"""
        analysis = []
        
        # Parse context for key metrics
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
        """Generate group analysis without AI"""
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


# Global instance
llama_handler = LlamaHandler()
