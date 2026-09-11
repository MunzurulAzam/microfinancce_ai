import os
import unittest
from datetime import date
from unittest.mock import patch
from flask import Flask
from reports import service as s
from reports.api import reports_bp
from ask_ai.api import ask_ai_bp
from core.cloud import configuration_status, generate

ROWS = [{'SnapshotDate':date(2026,8,31),'CountryCode':c,'SnapshotRows':10} for c in ['UG','KY','TZ','ZM']] + [{'SnapshotDate':date(2026,7,31),'CountryCode':c,'SnapshotRows':10} for c in ['UG','KY','ZM']]
class PeriodTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__);app.register_blueprint(reports_bp,url_prefix='/api');app.register_blueprint(ask_ai_bp,url_prefix='/api');self.client=app.test_client()

    def test_period_catalog_coverage(self):
        with patch('reports.service.db.query',return_value=ROWS):
            r=self.client.get('/api/reports/group-performance/periods').json
            self.assertEqual([p['period'] for p in r['periods']],['2026-08','2026-07'])
            self.assertEqual(r['periods'][1]['missing_countries'],['TZ'])
            self.assertEqual(r['periods'][1]['coverage'],'partial')
        with patch('reports.service.db.query',return_value=[]) as q:
            self.assertEqual(self.client.get('/api/reports/group-performance/periods?country=TZ').json['periods'],[])
            self.assertIn('TZ',q.call_args.args[1])
        self.assertEqual(self.client.get('/api/reports/group-performance/periods?country=BAD').status_code,400)

    def test_warehouse_error_is_not_empty_catalog(self):
        with patch('reports.service.db.query',side_effect=s.db.QueryError('offline')):
            r=self.client.get('/api/reports/group-performance/periods');self.assertEqual(r.status_code,503)
            self.assertNotIn('periods',r.json);self.assertEqual(r.json['code'],'warehouse_unavailable')

    def test_missing_period_enriched_on_both_routes(self):
        for endpoint,body in [('/api/ask-ai',{'question':'Group Performance Report January 2025'}),('/api/reports/group-performance',{'period':'2025-01'})]:
            with patch('reports.service.read_month',return_value=([],[])),patch('reports.service.db.query',return_value=ROWS):
                r=self.client.post(endpoint,json=body)
                self.assertEqual(r.status_code,422);self.assertEqual(r.json['code'],'report_data_missing')
                self.assertEqual(r.json['available_periods'][0]['period'],'2026-08')
                self.assertFalse(r.json['retryable'])

    def test_date_formats_and_historical_year(self):
        for text in ['Group Performance Report July 2026','গ্রুপ পারফরম্যান্স রিপোর্ট জুলাই ২০২৬','Group Performance Report 2026-7']:
            self.assertEqual(s.parse_question(text),'2026-07')
        self.assertEqual(s.parse_question('Group Performance Report December 1999'),'1999-12')
        self.assertEqual(s.normalize_period('২০২৬-৭'),'2026-07')
        with self.assertRaises(s.ReportError) as e:s.period_end(date.today().strftime('%Y-%m'))
        self.assertEqual(e.exception.code,'period_incomplete')

    def test_arbitrary_period_reaches_queries_and_previous_year(self):
        from tests.test_cloud_reports import rows
        out,par=rows()
        with patch('reports.service.read_month',side_effect=[(out,par),([],[])] ) as read,patch('reports.service.save_report'):
            r=s.create_report('2025-1','UG',False)['report']
            self.assertEqual(r['period'],'2025-01');self.assertEqual(r['comparison_period'],'2024-12')
            self.assertEqual(read.call_args_list[0].args[0],date(2025,1,31))
            self.assertIsNone(r['previous_countries'][0]['principal_local'])

    def test_sql_cloud_error_keeps_code_and_retryability(self):
        with patch.dict(os.environ,{'OLLAMA_TRANSPORT':'direct_cloud', 'OLLAMA_API_KEY':'', 'GROQ_API_KEY':''}),patch('ask_ai.engine.build_prompt',return_value='prompt'):
            r=self.client.post('/api/ask-ai',json={'question':'how many branch','country':'UG'})
            self.assertEqual(r.status_code,503);self.assertEqual(r.json['code'],'cloud_not_configured');self.assertFalse(r.json['retryable'])
            self.assertFalse(configuration_status()['configured'])

    def test_report_then_new_question_still_uses_sql(self):
        context=[{'role':'assistant','text':'Report ready','metadata':{'report_type':'group-performance','period':'2026-08','country':'UG'}}]
        with patch('ask_ai.engine.ask',return_value={'success':True,'answer':'12'}) as sql:
            r=self.client.post('/api/ask-ai',json={'question':'how many branch','country':'UG','context':context})
            self.assertEqual(r.json['mode'],'sql');sql.assert_called_once()

if __name__=='__main__':unittest.main()
