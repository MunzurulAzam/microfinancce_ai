"""Local UI-test server. Synthetic data only; never imports database connections."""
from flask import Flask, request, jsonify
from flask_cors import CORS
import time
app = Flask(__name__)
CORS(app)
@app.post('/api/ask')
@app.post('/api/ask-ai')
def ask():
    body = request.get_json()
    question = body['question']
    if 'missing key' in question.lower():
        return jsonify(success=False,error='Set OLLAMA_API_KEY on the Python server.',code='cloud_not_configured',retryable=False),503
    if '2025' in question:
        return jsonify(success=False,error='No historical snapshot exists for 2025.',code='report_data_missing',retryable=False,country='ALL',available_periods=[{'period':'2026-07','coverage':'partial','missing_countries':['TZ']}]),422
    if 'slow' in question.lower(): time.sleep(15)
    meta = {'resolved_question':question,'country':body.get('country') or 'ALL'}
    if 'report' in question.lower():
        meta.update(report_type='group-performance',period='2026-08')
        report = {'report_id':'missing-fixture-snapshot','period':'2026-08','period_label':'August 2026','comparison_label':'July 2026','country':meta['country'],'metrics':{'countries':1,'branches':12,'borrowers':120,'principal_usd':None,'par_percent':2,'par_amount_usd':None},'availability':{'warnings':['Synthetic browser test data']},'countries':[{'country':'UG','name':'Uganda','growth_percent':3,'portfolio_share_percent':None}], 'sections':[{'id':'executive','title':'Executive summary','paragraphs':['Synthetic report preview for browser testing.']},{'id':'table','title':'Network','table':{'columns':['Country','Branches'],'rows':[['Uganda',12]]}}], 'sources':[],'generated_at':'2026-09-10'}
        return jsonify(success=True,mode='report',report=report,context_metadata=meta,resolved_question=question)
    return jsonify(success=True,answer='Synthetic answer: '+question,columns=['Country','Branches'],rows=[{'Country':'Uganda','Branches':12}],row_count=1,sql='SELECT Country, Branches FROM approved_view',context_metadata=meta,resolved_question=question)
@app.get('/api/reports/<report_id>/pdf')
def missing(report_id): return jsonify(error='Snapshot unavailable'),404
@app.get('/api/reports/group-performance/periods')
def periods(): return jsonify(success=True,country=request.args.get('country','ALL'),periods=[{'period':'2026-08','coverage':'all_selected_countries','missing_countries':[]},{'period':'2026-07','coverage':'partial','missing_countries':['TZ']}])
if __name__=='__main__': app.run(port=5091,threaded=True)
