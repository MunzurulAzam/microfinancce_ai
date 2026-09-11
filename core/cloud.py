"""Shared cloud inference: free Ollama models first, then an optional free Groq fallback."""
import os
import time
import requests
from urllib.parse import urlparse

GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'


def model_for(task):
    names = {'sql': 'ASK_AI_MODEL', 'report': 'REPORT_AI_MODEL', 'vision': 'OLLAMA_VISION_MODEL'}
    default = 'gemma4:31b' if task == 'vision' else 'gpt-oss:120b'
    value = os.getenv(names.get(task, 'OLLAMA_MODEL'), default)
    return cloud_model_name(value)

def cloud_model_name(value):
    if os.getenv('OLLAMA_TRANSPORT', 'local_cloud') == 'direct_cloud':
        return value.removesuffix('-cloud').removesuffix(':cloud')
    if value.endswith(('-cloud', ':cloud')):
        return value
    return value + ('-cloud' if ':' in value else ':cloud')


def chain_for(task, model=None):
    first = cloud_model_name(model) if model else model_for(task)
    chain = [('ollama', first)]
    if task == 'vision':
        return chain
    fallback = os.getenv('OLLAMA_FALLBACK_MODEL', 'nemotron-3-super').strip()
    if fallback and cloud_model_name(fallback) != first:
        chain.append(('ollama', cloud_model_name(fallback)))
    if os.getenv('GROQ_API_KEY', '').strip():
        chain.append(('groq', os.getenv('GROQ_MODEL', '').strip() or 'openai/gpt-oss-120b'))
    return chain


def fail(code, message, status=503):
    return {'success': False, 'text': None, 'error': message, 'code': code,
            'http_status': status, 'retryable': code not in {'cloud_not_configured', 'cloud_configuration', 'cloud_authentication', 'cloud_model_unavailable', 'cloud_access_required'}, 'unavailable': True, 'overloaded': code == 'rate_limited'}


def connection_settings():
    transport = os.getenv('OLLAMA_TRANSPORT', 'local_cloud')
    if transport == 'local_cloud':
        base = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
        parsed = urlparse(base)
        if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'} or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return None, {}, fail('cloud_configuration', 'OLLAMA_BASE_URL must point to the local Ollama HTTP server.')
        return base, {}, None
    if transport != 'direct_cloud':
        return None, {}, fail('cloud_configuration', 'OLLAMA_TRANSPORT must be local_cloud or direct_cloud.')
    key = os.getenv('OLLAMA_API_KEY', '').strip()
    if not key:
        return None, {}, fail('cloud_not_configured', 'Set OLLAMA_API_KEY on the Python server for direct cloud access.')
    base = os.getenv('OLLAMA_CLOUD_BASE_URL', 'https://ollama.com').rstrip('/')
    if base != 'https://ollama.com':
        return None, {}, fail('cloud_configuration', 'OLLAMA_CLOUD_BASE_URL must be https://ollama.com.')
    return base, {'Authorization': f'Bearer {key}'}, None


def configuration_status():
    _, _, error = connection_settings()
    groq = bool(os.getenv('GROQ_API_KEY', '').strip())
    return {'configured': error is None or groq, 'transport': os.getenv('OLLAMA_TRANSPORT', 'local_cloud'),
            'code': error['code'] if error else 'configured', 'authentication_verified': False,
            'groq_configured': groq}


def _reasoning(model, task):
    # gpt-oss ignores think=false, so give it an explicit effort and token headroom instead.
    return ('medium' if task == 'sql' else 'low') if 'gpt-oss' in model else None


def _post(url, payload, headers, deadline, offline):
    for attempt in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, fail('cloud_timeout', 'Cloud model timed out. Please retry.', 504)
        try:
            response = requests.post(url, json=payload, headers=headers,
                                     timeout=(min(5, remaining), remaining))
        except requests.Timeout:
            return None, fail('cloud_timeout', 'Cloud model timed out. Please retry.', 504)
        except requests.RequestException:
            return None, fail('cloud_unavailable', offline)
        if response.status_code in (429, 503) and attempt < 2:
            time.sleep(min(2 ** attempt, max(0, deadline - time.monotonic())))
            continue
        return response, None


def _ollama(model, prompt, *, task, temperature, num_predict, deadline, images, json_mode):
    base, headers, error = connection_settings()
    if error:
        return error
    local_proxy = os.getenv('OLLAMA_TRANSPORT', 'local_cloud') == 'local_cloud'
    message = {'role': 'user', 'content': prompt}
    if images:
        message['images'] = images
    effort = _reasoning(model, task)
    payload = {'model': model, 'messages': [message], 'stream': False, 'think': effort or False,
               'options': {'temperature': temperature, 'num_predict': num_predict + (1024 if effort else 0)}}
    if json_mode:
        payload['format'] = 'json'
    response, error = _post(base + '/api/chat', payload, headers, deadline,
                            'Cannot connect to local Ollama. Start Ollama on the Python host.' if local_proxy else 'Cannot connect to Ollama Cloud.')
    if error:
        return error
    if response.status_code == 200:
        try:
            data = response.json()
            content = data['message']['content']
            if not isinstance(content, str) or not content.strip() or data.get('done_reason') == 'length':
                raise ValueError('Incomplete content')
        except (ValueError, KeyError, TypeError):
            return fail('cloud_invalid_response', 'Cloud returned an empty, incomplete or invalid response.', 502)
        return {'success': True, 'text': content.strip(), 'error': None, 'model': model, 'provider': 'ollama'}
    if response.status_code in (401, 403):
        return fail('cloud_authentication', 'Sign in to the local Ollama app on the Python host to use cloud models.' if local_proxy else 'Ollama Cloud API key is invalid or lacks access.')
    if response.status_code == 402:
        return fail('cloud_access_required', 'This Ollama cloud model requires an eligible subscription or usage credits on the signed-in account.', 402)
    if response.status_code == 404:
        return fail('cloud_model_unavailable', 'Cloud model is not available in local Ollama. Pull the configured cloud model tag.' if local_proxy else 'Configured cloud model is unavailable; check server model settings.')
    return fail('rate_limited' if response.status_code == 429 else 'cloud_unavailable',
                'Ollama Cloud is busy. Please retry shortly.')


def _groq(model, prompt, *, task, temperature, num_predict, deadline, images, json_mode):
    key = os.getenv('GROQ_API_KEY', '').strip()
    if not key:
        return fail('cloud_not_configured', 'Set GROQ_API_KEY on the Python server for the Groq fallback.')
    if images:
        return fail('cloud_model_unavailable', 'The Groq fallback does not accept images.')
    effort = _reasoning(model, task)
    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': temperature,
               'max_completion_tokens': num_predict + (1024 if effort else 0)}
    if effort:
        payload.update(reasoning_effort=effort, include_reasoning=False)
    elif 'qwen' in model:
        payload.update(reasoning_format='hidden', max_completion_tokens=num_predict + 1024)
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    response, error = _post(GROQ_URL, payload, {'Authorization': f'Bearer {key}'}, deadline, 'Cannot connect to Groq.')
    if error:
        return error
    if response.status_code == 200:
        try:
            choice = response.json()['choices'][0]
            content = choice['message']['content']
            if not isinstance(content, str) or not content.strip() or choice.get('finish_reason') == 'length':
                raise ValueError('Incomplete content')
        except (ValueError, KeyError, TypeError, IndexError):
            return fail('cloud_invalid_response', 'Cloud returned an empty, incomplete or invalid response.', 502)
        return {'success': True, 'text': content.strip(), 'error': None, 'model': model, 'provider': 'groq'}
    if response.status_code in (401, 403):
        return fail('cloud_authentication', 'Groq API key is invalid or lacks access.')
    if response.status_code == 404:
        return fail('cloud_model_unavailable', 'Configured Groq model is unavailable; check GROQ_MODEL.')
    if response.status_code in (413, 429):
        return fail('rate_limited', 'Groq free tier is busy. Please retry shortly.')
    return fail('cloud_unavailable', 'Groq is unavailable.')


def call(provider, model, prompt, *, task='text', temperature=0, num_predict=1200,
         timeout=60, deadline=None, images=None, json_mode=False):
    send = _groq if provider == 'groq' else _ollama
    return send(model, prompt, task=task, temperature=temperature, num_predict=num_predict,
                deadline=deadline or time.monotonic() + timeout, images=images, json_mode=json_mode)


def generate(prompt, *, task='text', model=None, temperature=0, num_predict=1200,
             timeout=60, images=None, json_mode=False):
    deadline = time.monotonic() + timeout
    chain = chain_for(task, model)
    first = None
    for provider, name in chain[:1] if images else chain:
        if first and deadline - time.monotonic() < 3:
            break
        result = call(provider, name, prompt, task=task, temperature=temperature, num_predict=num_predict,
                      deadline=deadline, images=images, json_mode=json_mode)
        if result['success']:
            return result
        first = first or result
    return first
