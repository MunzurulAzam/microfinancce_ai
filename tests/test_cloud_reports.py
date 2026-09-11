import copy
import json
import os
import tempfile
import unittest
from decimal import Decimal
from unittest.mock import Mock, patch
import requests
from flask import Flask
from core.cloud import generate, model_for
from reports import service as s
from reports.api import reports_bp
from ask_ai.api import ask_ai_bp


def rows(code='UG', balance=1000, risk=100):
    return ([{'CountryCode': code, 'BranchId': 1, 'BranchName': 'Branch One', 'ForexRate': 1,
              'TotalBorrowersTotal': 10, 'PrincipalOSTotal': balance}],
            [{'CountryCode': code, 'BranchId': 1, 'PrincipalAmount': balance,
              'PrincipalOSAbove30': risk, 'PARAbove30': risk / balance * 100}])


class CloudTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'OLLAMA_TRANSPORT':'direct_cloud', 'OLLAMA_API_KEY': 'test-key', 'OLLAMA_CLOUD_BASE_URL': 'https://ollama.com', 'OLLAMA_FALLBACK_MODEL': '', 'GROQ_API_KEY': ''})
        env.start(); self.addCleanup(env.stop)

    @patch('core.cloud.requests.post')
    def test_cloud_transport(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'message': {'content': 'ok'}}
        self.assertTrue(generate('question', task='vision', images=['abc'])['success'])
        self.assertEqual(post.call_args.args[0], 'https://ollama.com/api/chat')
        self.assertEqual(post.call_args.kwargs['json']['messages'][0]['images'], ['abc'])
        self.assertNotIn('keep_alive', post.call_args.kwargs['json'])
        self.assertEqual(model_for('sql'), 'gpt-oss:120b')

    @patch('core.cloud.requests.post')
    def test_missing_key(self, post):
        with patch.dict(os.environ, {'OLLAMA_API_KEY': ''}):
            self.assertEqual(generate('x')['code'], 'cloud_not_configured')
        post.assert_not_called()

    @patch('core.cloud.time.sleep')
    @patch('core.cloud.requests.post')
    def test_errors_retries(self, post, sleep):
        for status, attempts, code in [(401,1,'cloud_authentication'), (403,1,'cloud_authentication'),
                                       (404,1,'cloud_model_unavailable'), (429,3,'rate_limited'), (503,3,'cloud_unavailable')]:
            post.reset_mock(); post.return_value = Mock(status_code=status)
            self.assertEqual(generate('x')['code'], code)
            self.assertEqual(post.call_count, attempts)


    @patch('document_verification.vision_client.generate')
    def test_vision_classifier_and_extractor_modes(self, call):
        from document_verification.vision_client import call_vision
        call.return_value = {'success': True, 'text': 'YES'}
        call_vision('base64', 'YES or NO')
        self.assertFalse(call.call_args.kwargs['json_mode'])
        call_vision('base64', 'JSON fields', json_mode=True)
        self.assertTrue(call.call_args.kwargs['json_mode'])
        self.assertEqual(call.call_args.kwargs['task'], 'vision')

    @patch('core.llm.generate')
    def test_legacy_text_client_uses_cloud(self, call):
        from core.llm import llama_handler
        call.return_value = {'success':True, 'text':'Verified analysis'}
        self.assertEqual(llama_handler.analyze_with_ai('analyze', 'facts'), 'Verified analysis')
        self.assertEqual(call.call_args.kwargs['task'], 'text')

    @patch('core.cloud.requests.post')
    def test_timeout_malformed(self, post):
        post.side_effect = requests.Timeout()
        self.assertEqual(generate('x')['http_status'], 504)
        post.side_effect = None
        for data in [None, {}, {'message': {'content': ''}}, {'message': {'content': 'partial'}, 'done_reason':'length'}]:
            post.return_value = Mock(status_code=200)
            post.return_value.json.return_value = data
            self.assertEqual(generate('x')['code'], 'cloud_invalid_response')


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        env = patch.dict(os.environ, {'REPORT_STORAGE_DIR': self.directory.name, 'REPORT_FX_FILE': '', 'OLLAMA_API_KEY': ''})
        env.start(); self.addCleanup(env.stop)
        app = Flask(__name__); app.register_blueprint(reports_bp, url_prefix='/api'); app.register_blueprint(ask_ai_bp, url_prefix='/api')
        self.client = app.test_client()

    def test_alias_period(self):
        self.assertTrue(s.REPORT_NAMES.search('গ্রুপ পারফরম্যান্স রিপোর্ট আগস্ট ২০২৬'))
        self.assertEqual(s.parse_question('গ্রুপ পারফরম্যান্স রিপোর্ট আগস্ট ২০২৬'), '2026-08')
        self.assertEqual(s.parse_question('Group Portfolio Report August 2026'), '2026-08')
        self.assertIsNone(s.parse_question('Group Performance Report'))
        self.assertEqual(s.parse_question('Group Performance Report 2026-7'), '2026-07')
        for q in ['Group Performance Report August', 'Group Performance Report 2026']:
            with self.assertRaises(s.ReportError): s.parse_question(q)
        for period in ['2026-13', [], '2026-00', '9999-12']:
            with self.assertRaises(s.ReportError): s.period_end(period)

    def test_duplicates_and_par_reconciliation(self):
        out, par = rows(); out.append(copy.deepcopy(out[0]))
        result, warnings = s.summarize_month(out, par, ['UG'], '2026-08', {})
        self.assertIsNone(result[0]['principal_local']); self.assertTrue(warnings)
        out, par = rows(); par[0]['PrincipalAmount'] = 999
        result, _ = s.summarize_month(out, par, ['UG'], '2026-08', {})
        self.assertIsNone(result[0]['par_percent']); self.assertEqual(result[0]['principal_local'], 1000)

    def test_weighted_par_fx_zero(self):
        ug, ugpar = rows('UG', 1000, 100); ky, kypar = rows('KY', 3000, 60)
        rates = {'2026-08': {c: {'local_per_usd': 10, 'source':'approved monthly rates'} for c in ['UG','KY']}}
        result, _ = s.summarize_month(ug+ky, ugpar+kypar, ['UG','KY'], '2026-08', rates)
        self.assertEqual(s.aggregate(result)['principal_usd'], 400)
        self.assertEqual(s.aggregate(result)['par_percent'], 4)
        result, _ = s.summarize_month(ug+ky, ugpar+kypar, ['UG','KY'], '2026-08', {})
        self.assertIsNone(s.aggregate(result)['principal_usd'])
        self.assertIsNone(s.ratio(Decimal(1), Decimal(0)))

    @patch('reports.service.read_month')
    def test_snapshot_previous_year_pdf(self, read):
        read.side_effect = [rows(), ([],[])]
        response = self.client.post('/api/reports/group-performance', json={'period':'2026-01','country':'UG','summary':False})
        self.assertEqual(response.status_code, 200, response.json)
        report = response.json['report']
        self.assertEqual(report['comparison_period'], '2025-12')
        self.assertIsNone(report['previous_metrics']['borrowers'])
        self.assertEqual(s.load_report(report['report_id']), report)
        read.reset_mock()
        download = self.client.get(report['pdf_url'])
        self.assertEqual(download.status_code, 200); self.assertTrue(download.data.startswith(b'%PDF'))
        read.assert_not_called()
        self.assertEqual(self.client.get('/api/reports/bad/pdf').status_code,404)

    @patch('reports.service.read_month')
    @patch('reports.service.available_periods')
    def test_default_routing(self, available, read):
        available.return_value = ['2026-08']; read.return_value = rows()
        result = self.client.post('/api/ask-ai', json={'question':'Group Performance Report','country':'UG','summary':False})
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['mode'],'report'); self.assertEqual(result.json['report']['period'],'2026-08')
        available.return_value = []
        self.assertEqual(self.client.post('/api/ask-ai',json={'question':'Group Performance Report'}).status_code,422)

    @patch('reports.service.read_month')
    def test_database_unavailable(self, read):
        read.side_effect = s.db.QueryError('secret host details')
        response = self.client.post('/api/reports/group-performance', json={'period':'2026-08'})
        self.assertEqual(response.status_code,503); self.assertNotIn('secret',response.json['error'])
        self.assertEqual(os.listdir(self.directory.name),[])

    @patch('reports.service.read_month')
    @patch('reports.service.generate')
    def test_untrusted_narrative(self, generate_mock, read):
        read.return_value = rows()
        generate_mock.return_value = {'success':True,'text':'{"indices":["ignore all rules",900]}'}
        report = s.create_report('2026-08','UG')['report']
        self.assertEqual(report['narrative_mode'],'template'); self.assertNotIn('ignore all rules',json.dumps(report))


    @patch('reports.service.read_month')
    def test_primary_ask_endpoint(self, read):
        from assistant.routes import ask_bp
        app = Flask(__name__); app.register_blueprint(ask_bp, url_prefix='/api')
        read.return_value = rows()
        response = app.test_client().post('/api/ask', json={'question':'Group Performance Report August 2026','country':'UG','summary':False})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['mode'], 'report')

    def test_query_scope_and_date_parameters(self):
        with patch('reports.service.db.query', return_value=[]) as query:
            s.read_month(s.period_end('2026-08'), ['UG'])
            self.assertEqual(query.call_count, 2)
            for call in query.call_args_list:
                self.assertIn('CountryCode IN (%s)', call.args[0])
                self.assertEqual(call.args[1], ('2026-08-31', 'UG'))
                self.assertNotIn('JOIN', call.args[0])

    def test_missing_country_and_duplicate_par(self):
        out, par = rows(); par.append(copy.deepcopy(par[0]))
        current, _ = s.summarize_month(out, par, ['UG','KY'], '2026-08', {})
        self.assertIsNone(current[0]['branch_details'][0]['par_percent'])
        self.assertFalse(current[1]['snapshot_available'])
        self.assertIsNone(s.aggregate(current)['borrowers'])

    def test_input_types(self):
        for payload in [[], None, {'question': 12}, {'question':'x','summary':'false'}, {'question':'x','country':False}]:
            self.assertEqual(self.client.post('/api/ask-ai',json=payload).status_code,400)
        for payload in [[], {'period':[]}, {'country':[],'period':'2026-08'}, {'period':'2026-08','summary':'yes'}]:
            self.assertEqual(self.client.post('/api/reports/group-performance',json=payload).status_code,400)


if __name__ == '__main__': unittest.main()
