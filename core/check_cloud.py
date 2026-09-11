"""Run `python -m core.check_cloud` on the Python host; never prints credentials."""
import json
from pathlib import Path
from dotenv import load_dotenv
from core.cloud import call, chain_for, configuration_status


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    status = configuration_status()
    if status['configured']:
        status['providers'] = []
        for task in ('sql', 'vision'):
            for provider, model in chain_for(task):
                response = call(provider, model, 'Reply with OK.', task=task, timeout=30, num_predict=20)
                status['providers'].append({'task': task, 'provider': provider, 'model': model,
                                            'code': 'cloud_ready' if response['success'] else response['code']})
        sql = [p for p in status['providers'] if p['task'] == 'sql']
        ready = any(p['code'] == 'cloud_ready' for p in sql)
        status.update(authentication_verified=ready, code='cloud_ready' if ready else sql[0]['code'])
    print(json.dumps(status))
    return 0 if status.get('authentication_verified') else 1


if __name__ == '__main__':
    raise SystemExit(main())
