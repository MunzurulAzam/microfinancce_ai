import os
import unittest
from unittest.mock import patch, Mock
import requests
from core.cloud import call, chain_for, generate, model_for, configuration_status

class LocalCloudTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{'OLLAMA_TRANSPORT':'local_cloud','OLLAMA_BASE_URL':'http://127.0.0.1:11434','OLLAMA_API_KEY':'must-not-be-forwarded','ASK_AI_MODEL':'qwen3.5:397b','OLLAMA_VISION_MODEL':'minimax-m3','OLLAMA_FALLBACK_MODEL':'','GROQ_API_KEY':''})
        p.start();self.addCleanup(p.stop)

    @patch('core.cloud.requests.post')
    def test_proxy_uses_cloud_tag_without_bearer(self,post):
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={'message':{'content':'OK'}}
        with patch.dict(os.environ,{'OLLAMA_API_KEY':''}):
            self.assertTrue(generate('hello',task='sql')['success'])
            self.assertTrue(configuration_status()['configured'])
        self.assertEqual(post.call_args.args[0],'http://127.0.0.1:11434/api/chat')
        self.assertEqual(post.call_args.kwargs['headers'],{})
        self.assertEqual(post.call_args.kwargs['json']['model'],'qwen3.5:397b-cloud')
        self.assertEqual(model_for('vision'),'minimax-m3:cloud')

    @patch('core.cloud.requests.post')
    def test_proxy_auth_and_credit_errors(self,post):
        post.return_value=Mock(status_code=401)
        self.assertIn('Sign in',generate('hello')['error'])
        post.return_value=Mock(status_code=402)
        result=generate('hello');self.assertEqual(result['code'],'cloud_access_required');self.assertFalse(result['retryable'])

    @patch('core.cloud.requests.post')
    def test_reject_nonlocal_proxy(self,post):
        with patch.dict(os.environ,{'OLLAMA_BASE_URL':'http://example.com:11434'}):
            self.assertEqual(generate('hello')['code'],'cloud_configuration')
        post.assert_not_called()

    def test_cloud_tags_are_idempotent(self):
        with patch.dict(os.environ,{'ASK_AI_MODEL':'qwen3.5:397b-cloud'}):self.assertEqual(model_for('sql'),'qwen3.5:397b-cloud')
        with patch.dict(os.environ,{'ASK_AI_MODEL':'qwen3.5:cloud'}):self.assertEqual(model_for('sql'),'qwen3.5:cloud')

class StarterDefaultsTests(unittest.TestCase):
    def test_default_models(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(model_for('sql'), 'gpt-oss:120b-cloud')
            self.assertEqual(model_for('text'), 'gpt-oss:120b-cloud')
            self.assertEqual(model_for('report'), 'gpt-oss:120b-cloud')
            self.assertEqual(model_for('vision'), 'gemma4:31b-cloud')
            self.assertEqual(chain_for('sql'), [('ollama','gpt-oss:120b-cloud'),('ollama','nemotron-3-super:cloud')])

class FallbackTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{'OLLAMA_TRANSPORT':'local_cloud','OLLAMA_BASE_URL':'http://127.0.0.1:11434','ASK_AI_MODEL':'gpt-oss:120b','OLLAMA_MODEL':'gpt-oss:120b','OLLAMA_VISION_MODEL':'gemma4:31b','OLLAMA_FALLBACK_MODEL':'nemotron-3-super','GROQ_API_KEY':'groq-key','GROQ_MODEL':''})
        p.start();self.addCleanup(p.stop)

    @staticmethod
    def ok(text='OK'):
        response=Mock(status_code=200);response.json.return_value={'message':{'content':text}};return response

    def test_chain_for(self):
        self.assertEqual(chain_for('sql'),[('ollama','gpt-oss:120b-cloud'),('ollama','nemotron-3-super:cloud'),('groq','openai/gpt-oss-120b')])
        self.assertEqual(chain_for('vision'),[('ollama','gemma4:31b-cloud')])
        with patch.dict(os.environ,{'GROQ_API_KEY':'','OLLAMA_FALLBACK_MODEL':'gpt-oss:120b'}):
            self.assertEqual(chain_for('text'),[('ollama','gpt-oss:120b-cloud')])

    @patch('core.cloud.requests.post')
    def test_reasoning_effort_per_model(self,post):
        post.return_value=self.ok()
        generate('q',task='sql');self.assertEqual(post.call_args.kwargs['json']['think'],'medium')
        self.assertEqual(post.call_args.kwargs['json']['options']['num_predict'],1200+1024)
        generate('q',task='text',num_predict=40);self.assertEqual(post.call_args.kwargs['json']['think'],'low')
        generate('q',task='vision',images=['abc']);self.assertIs(post.call_args.kwargs['json']['think'],False)
        self.assertEqual(post.call_args.kwargs['json']['options']['num_predict'],1200)

    @patch('core.cloud.time.sleep')
    @patch('core.cloud.requests.post')
    def test_busy_primary_falls_back_to_free_ollama_model(self,post,sleep):
        post.side_effect=[Mock(status_code=429)]*3+[self.ok('fallback')]
        result=generate('q',task='sql')
        self.assertEqual((result['provider'],result['model'],result['text']),('ollama','nemotron-3-super:cloud','fallback'))
        self.assertIs(post.call_args.kwargs['json']['think'],False)

    @patch('core.cloud.requests.post')
    def test_ollama_down_uses_groq(self,post):
        groq=Mock(status_code=200);groq.json.return_value={'choices':[{'message':{'content':'{"a":1}'},'finish_reason':'stop'}]}
        post.side_effect=[requests.ConnectionError(),requests.ConnectionError(),groq]
        result=generate('q',task='text',json_mode=True)
        self.assertEqual((result['provider'],result['model'],result['text']),('groq','openai/gpt-oss-120b','{"a":1}'))
        self.assertEqual(post.call_args.args[0],'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(post.call_args.kwargs['headers'],{'Authorization':'Bearer groq-key'})
        body=post.call_args.kwargs['json']
        self.assertEqual((body['reasoning_effort'],body['include_reasoning'],body['response_format']),('low',False,{'type':'json_object'}))

    @patch('core.cloud.requests.post')
    def test_vision_never_leaves_ollama(self,post):
        post.return_value=Mock(status_code=402)
        self.assertEqual(generate('q',task='vision',images=['abc'])['code'],'cloud_access_required')
        self.assertEqual(post.call_count,1)

    @patch('core.cloud.requests.post')
    def test_all_fail_returns_primary_error(self,post):
        post.return_value=Mock(status_code=401)
        result=generate('q',task='sql')
        self.assertIn('Sign in',result['error']);self.assertEqual(post.call_count,3)

    @patch('core.cloud.requests.post')
    def test_groq_truncated_or_unauthorized(self,post):
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={'choices':[{'message':{'content':'SELECT'},'finish_reason':'length'}]}
        self.assertEqual(call('groq','openai/gpt-oss-120b','q')['code'],'cloud_invalid_response')
        post.return_value=Mock(status_code=401)
        self.assertEqual(call('groq','openai/gpt-oss-120b','q')['code'],'cloud_authentication')

    def test_groq_counts_as_configured(self):
        with patch.dict(os.environ,{'OLLAMA_TRANSPORT':'direct_cloud','OLLAMA_API_KEY':''}):
            status=configuration_status()
        self.assertTrue(status['configured']);self.assertTrue(status['groq_configured'])
