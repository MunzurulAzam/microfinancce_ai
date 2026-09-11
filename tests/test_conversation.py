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

    def test_member_code_is_never_rewritten(self):
        for question in ['now give me information of this CLN0000109', 'now give me details for this member: CLN0000109', 'give me group size of that CLN0000109 client']:
            with self.subTest(question=question), patch('core.conversation.generate') as cloud:
                self.assertEqual(resolve(question, REPORT), (question, None, None))
                self.assertIsNone(resolve(question)[2])
                cloud.assert_not_called()

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

MEMBER = [{'MemberId': 109, 'MemberCode': 'CLN0000109', 'CountryCode': 'UG', 'GroupId': 7}]

class MemberRoutingTests(unittest.TestCase):
    def test_intent_split(self):
        from ask_ai.engine import is_member_analysis
        for q in ['now give me details for this member: CLN0000109', 'now give me information of this CLN0000109 member report', 'give me information of CLN0000109 this client', 'credit score for CLN0000109', 'can CLN0000109 get a loan?', 'CLN0000109', '1090', 'CLN0000109 এর তথ্য দাও']:
            with self.subTest(q=q): self.assertTrue(is_member_analysis(q))
        for q in ['give me group size of this CLN0000109 client', 'all loans of CLN0000109', 'which branch is CLN0000109 in', 'CLN0000109 এর গ্রুপ সাইজ কত']:
            with self.subTest(q=q): self.assertFalse(is_member_analysis(q))

    @patch('ask_ai.member_analysis.resolve_member', return_value=MEMBER)
    @patch('ask_ai.engine.ask', return_value={'success': True, 'answer': '12', 'rows': []})
    def test_fact_question_uses_member_scoped_sql(self, ask, resolve_member):
        from ask_ai.engine import route
        result = route('give me group size of this CLN0000109 client', country='ALL')
        resolve_member.assert_called_once_with('CLN0000109', None)
        ask.assert_called_once_with('give me group size of this CLN0000109 client', country='UG', with_summary=True, member=MEMBER[0])
        self.assertEqual((result['mode'], result['entity']), ('sql', 'CLN0000109'))

    @patch('ask_ai.member_analysis.analyze_member', return_value={'success': True, 'mode': 'member_analysis'})
    def test_profile_question_uses_analysis(self, analyze):
        from ask_ai.engine import route
        self.assertEqual(route('now give me information of this CLN0000109 member report')['mode'], 'member_analysis')
        analyze.assert_called_once()

    @patch('ask_ai.member_analysis.suggest_members', return_value=[])
    @patch('ask_ai.member_analysis.resolve_member', return_value=[])
    def test_unknown_member(self, *_):
        from ask_ai.engine import route
        result = route('group size of CLN9999999')
        self.assertFalse(result['success']); self.assertTrue(result['bad_request']); self.assertIn('CLN9999999', result['error'])

    @patch('ask_ai.prompt.schema_mod.get_schema_text', return_value='schema')
    @patch('ask_ai.prompt.schema_mod.get_table_names', return_value=['MfMember', 'MfGroup'])
    def test_prompt_pins_member(self, *_):
        from ask_ai.prompt import build_prompt, build_repair_prompt
        self.assertIn("MemberId = 109 AND CountryCode = 'UG'", build_prompt('group size of CLN0000109', member=MEMBER[0]))
        self.assertIn('MemberId = 109', build_repair_prompt('q', 'SELECT 1', 'err', member=MEMBER[0]))
        self.assertNotIn('ONE member', build_prompt('group size of CLN0000109'))

    def test_legacy_endpoint_routes_member_questions(self):
        from flask import Flask
        from assistant.routes import ask_bp
        app = Flask(__name__); app.register_blueprint(ask_bp, url_prefix='/api')
        with app.test_client() as client, patch('ask_ai.engine.route', return_value={'success': True, 'answer': 'x'}) as route:
            self.assertEqual(client.post('/api/ask', json={'question': 'group size of CLN0000109', 'country': 'ALL'}).status_code, 200)
            route.assert_called_once_with('group size of CLN0000109', country='ALL', with_summary=True)

if __name__ == '__main__': unittest.main()
