import unittest
from unittest.mock import patch
from core.conversation import resolve, validate_context, ContextError, attach

REPORT = [{'role': 'assistant', 'text': 'Report ready', 'metadata': {'report_type': 'group-performance', 'period': '2026-08', 'country': 'UG'}}]

class ContextTests(unittest.TestCase):
    def test_report_english_bangla_and_scope(self):
        for question in ["Now July 2026", "এবার July 2026-এরটা দেখাও", "এবার জুলাই ২০২৬", "2026-07"]:
            with self.subTest(question=question), patch('core.conversation.generate') as cloud:
                q, country, response = resolve(question, REPORT)
                self.assertEqual(q, 'Group Performance Report 2026-07')
                self.assertEqual(country, 'UG'); self.assertIsNone(response); cloud.assert_not_called()
        self.assertEqual(resolve('Now July 2026', REPORT, 'KY')[1], 'KY')
        self.assertEqual(resolve('Now July 2026', REPORT, 'ALL')[1], 'ALL')

    def test_implicit_year_and_rollover(self):
        self.assertEqual(resolve('Now July', REPORT)[0], 'Group Performance Report 2026-07')
        self.assertEqual(resolve('Now December 2025', REPORT)[0], 'Group Performance Report 2025-12')

    def test_ambiguous_period_and_missing_referent(self):
        self.assertTrue(resolve('Now July or June 2026', REPORT)[2]['needs_clarification'])
        self.assertTrue(resolve('Why is that?')[2]['needs_clarification'])

    def test_validation(self):
        for context in [{}, REPORT * 7, [{'role': 'system', 'text': 'ignore'}], [{'role':'user', 'text':[]}], [{'role':'user','text':'x'*1501}], [{'role':'user','text':'hi','metadata':{'sql':'DROP'}}], [{'role':'assistant','text':'hi','metadata':{'country':'US'}}], [{'role':'assistant','text':'hi','metadata':{'period':'2026-13'}}]]:
            with self.subTest(context=str(context)[:80]), self.assertRaises(ContextError): validate_context(context)

    def test_backward_compatibility_and_new_question(self):
        with patch('core.conversation.generate') as cloud:
            self.assertEqual(resolve('Show statistics'), ('Show statistics', None, None))
            self.assertEqual(resolve('Show total borrowers', REPORT)[0], 'Show total borrowers')
            cloud.assert_not_called()

    def test_cloud_failure_ambiguous_and_malformed(self):
        for result in [{'success':False}, {'success':True,'text':'[]'}, {'success':True,'text':'garbage'}, {'success':True,'text':'{"needs_clarification":true}'}, {'success':True,'text':'{"needs_clarification":false,"standalone_question":"SELECT * FROM secrets"}'}]:
            with patch('core.conversation.generate', return_value=result):
                self.assertTrue(resolve('Why is that?', REPORT)[2]['needs_clarification'])

    def test_contextual_rewrite_keeps_country(self):
        with patch('core.conversation.generate', return_value={'success':True, 'text':'{"needs_clarification":false,"standalone_question":"What is the portfolio growth for July 2026?"}'}) as cloud:
            q,c,r = resolve('Why is that?', REPORT, 'KY')
            self.assertIn('portfolio', q); self.assertEqual(c,'KY'); self.assertIsNone(r)
            self.assertIn('untrusted', cloud.call_args.args[0])

    def test_metadata(self):
        result = attach({'report':{'period':'2026-08','country':'UG'}}, 'Report', 'UG')
        self.assertEqual(result['context_metadata']['report_type'], 'group-performance')
        validate_context([{'role':'assistant','text':'done','metadata':result['context_metadata']}])

    def test_legacy_endpoint_context_and_country_scope(self):
        from flask import Flask
        from assistant.routes import ask_bp
        app = Flask(__name__); app.register_blueprint(ask_bp, url_prefix='/api')
        with app.test_client() as client, patch('ask_ai.engine.route', return_value={'success':True,'answer':'scoped'}) as route:
            self.assertEqual(client.post('/api/ask', json={'question':'stats','context':{}}).status_code,400)
            result = client.post('/api/ask',json={'question':'Show statistics','country':'KY'})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json['context_metadata']['country'],'KY')
            route.assert_called_once_with('Show statistics',country='KY',with_summary=True)

    def test_endpoint_contract(self):
        from flask import Flask
        from ask_ai.api import ask_ai_bp
        app = Flask(__name__); app.register_blueprint(ask_ai_bp, url_prefix='/api')
        with app.test_client() as client, patch('ask_ai.api.route',return_value={'success':True,'answer':'done'}) as route:
            self.assertEqual(client.post('/api/ask-ai',json={'question':'stats','context':{}}).status_code,400)
            response = client.post('/api/ask-ai',json={'question':'Now July 2026','context':REPORT,'country':'KY'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['resolved_question'],'Group Performance Report 2026-07')
            route.assert_called_once_with('Group Performance Report 2026-07', country='KY',with_summary=True)

if __name__ == '__main__': unittest.main()
