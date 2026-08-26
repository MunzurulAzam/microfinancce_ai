import requests
import json
from config import Config


def get_ai_analysis(score_result):
    try:
        prompt = _build_prompt(score_result)
        response = requests.post(
            f"{Config.OLLAMA_BASE_URL}/api/generate",
            json={
                'model': Config.OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'num_predict': 500,
                }
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            print(f"Ollama returned status {response.status_code}")
            return _fallback_analysis(score_result)

    except requests.exceptions.ConnectionError:
        print("Ollama not available, using fallback analysis")
        return _fallback_analysis(score_result)
    except Exception as e:
        print(f"Ollama error: {e}")
        return _fallback_analysis(score_result)


def _build_prompt(score_result):

    weak_params = []
    for cat_key in ['client_scoring']:
        for d in score_result[cat_key]['details']:
            if d['score'] <= 2:
                weak_params.append(f"- {d['parameter']}: {d['score']}/5 ({d['reason']})")

    strong_params = []
    for cat_key in ['client_scoring']:
        for d in score_result[cat_key]['details']:
            if d['score'] == 5:
                strong_params.append(f"- {d['parameter']}: {d['score']}/5 ({d['reason']})")

    weak_str = '\n'.join(weak_params) if weak_params else '- None'
    strong_str = '\n'.join(strong_params[:8]) if strong_params else '- None'

    return f"""You are a microfinance credit risk analyst. Analyze this credit score and provide a brief recommendation.

**Client:** {score_result['member_name']} ({score_result['member_code']})
**Overall Score:** {score_result['total_score']}/{score_result['max_score']} ({score_result['percentage']}%)
**Classification:** {score_result['classification']}

**Category Breakdown:**
- Client Score: {score_result['client_scoring']['score']}/{score_result['client_scoring']['max']} ({score_result['client_scoring']['percentage']}%)

**Weak Areas (score ≤ 2):**
{weak_str}

**Strong Areas (score = 5):**
{strong_str}

Provide a concise analysis (3-5 sentences) covering:
1. Overall credit risk assessment
2. Key concerns from weak areas
3. Recommendation (approve, conditional approve, or reject)
Keep it professional and specific to this client's data."""


def _fallback_analysis(score_result):
    classification = score_result['classification']
    percentage = score_result['percentage']
    name = score_result['member_name']

    weak = []
    for cat_key in ['client_scoring']:
        for d in score_result[cat_key]['details']:
            if d['score'] <= 2:
                weak.append(d['parameter'])

    strong = []
    for cat_key in ['client_scoring']:
        for d in score_result[cat_key]['details']:
            if d['score'] == 5:
                strong.append(d['parameter'])

    if classification == 'Excellent':
        verdict = f"{name} demonstrates excellent creditworthiness with a score of {percentage}%. "
        verdict += f"Strong performance across {len(strong)} parameters. "
        verdict += "✅ Recommendation: APPROVE — low risk client with strong indicators."
    elif classification == 'Good':
        verdict = f"{name} shows good credit standing at {percentage}%. "
        if weak:
            verdict += f"Minor concerns in: {', '.join(weak[:3])}. "
        verdict += "✅ Recommendation: APPROVE with standard monitoring."
    elif classification == 'Moderate Risk':
        verdict = f"{name} has a moderate risk profile at {percentage}%. "
        if weak:
            verdict += f"Key concerns: {', '.join(weak[:3])}. "
        verdict += "⚠️ Recommendation: CONDITIONAL APPROVE — require additional guarantees or reduced loan amount."
    else:
        verdict = f"{name} shows high credit risk at {percentage}%. "
        if weak:
            verdict += f"Critical issues: {', '.join(weak[:5])}. "
        verdict += "🚫 Recommendation: REJECT or require significant risk mitigation before approval."

    return verdict
