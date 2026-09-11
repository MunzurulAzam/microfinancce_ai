"""Rank free cloud models on text-to-SQL: `python3 -m ask_ai.check_models [provider/model ...]`."""
import os
import sys
import time
from unittest.mock import patch

from dotenv import load_dotenv

load_dotenv()

from ask_ai import db, prompt                                 # noqa: E402  (must follow load_dotenv)
from ask_ai.glossary import EXAMPLES, examples_text           # noqa: E402
from ask_ai.sql_guard import sanitize, strip_limit, UnsafeSQL  # noqa: E402
from core.cloud import call, cloud_model_name                 # noqa: E402

CANDIDATES = ['ollama/gpt-oss:120b', 'ollama/nemotron-3-super', 'ollama/nemotron-3-ultra', 'ollama/gpt-oss:20b']


def _held_out(question, sql):
    # Leave-one-out: the question under test must not appear among the prompt's examples.
    block = f"-- Question: {question}\n{sql}"

    def examples(tables=None, limit=8):
        text = examples_text(tables, limit + 1)
        return text.replace(block + '\n\n', '').replace('\n\n' + block, '').replace(block, '')
    return examples


def _norm(value):
    try:
        return f'{float(value):.2f}'
    except (TypeError, ValueError):
        return str(value).strip().lower()


def _cells(sql):
    _, rows, _ = db.run_sql(sql)
    return len(rows), {_norm(v) for row in rows for v in row.values()}


def _ask(provider, model, text):
    result = call(provider, model, text, task='sql', timeout=120)
    if not result['success'] and result['code'] == 'rate_limited':
        time.sleep(30)
        result = call(provider, model, text, task='sql', timeout=120)
    return result


def score(spec, gold):
    provider, model = spec.split('/', 1)
    model = cloud_model_name(model) if provider == 'ollama' else model
    valid = same = 0
    seconds = 0.0
    for question, sql in EXAMPLES:
        with patch.object(prompt, 'examples_text', _held_out(question, sql)):
            text = prompt.build_prompt(question)
        started = time.time()
        result = _ask(provider, model, text)
        elapsed = time.time() - started
        seconds += elapsed
        if not result['success']:
            print(f"FAIL    {result['code']:<24} {question}")
            continue
        try:
            statement = sanitize(strip_limit(result['text']))
        except UnsafeSQL as e:
            print(f"UNSAFE  {question}\n          {e}")
            continue
        ok, error, _ = db.validate_sql(statement)
        if not ok:
            print(f"INVALID {question}\n          {error}")
            continue
        valid += 1
        try:
            count, cells = _cells(statement)
        except db.QueryError as e:
            print(f"FAIL(run) {question}\n          {e}")
            continue
        expected = gold.get(question)
        match = expected is not None and count == expected[0] and expected[1] <= cells
        same += match
        print(f"{'ok     ' if match else 'diff   '} {elapsed:6.1f}s  {question}")
    n = len(EXAMPLES)
    print(f"== {spec}: {valid}/{n} valid, {same}/{n} same result, {seconds / n:.1f}s avg\n")
    return spec, valid, same, seconds / n


def main():
    groq = [f"groq/{os.getenv('GROQ_MODEL') or 'openai/gpt-oss-120b'}"] if os.getenv('GROQ_API_KEY', '').strip() else []
    specs = sys.argv[1:] or CANDIDATES + groq
    gold = {}
    for question, sql in EXAMPLES:
        try:
            gold[question] = _cells(sanitize(sql))
        except db.QueryError as e:
            print(f"SKIP gold  {question}\n          {e}")
    results = [score(spec, gold) for spec in specs]
    print('Ranking (same result, valid, latency):')
    for spec, valid, same, avg in sorted(results, key=lambda r: (-r[2], -r[1], r[3])):
        print(f"  {same:>2} same  {valid:>2} valid  {avg:5.1f}s  {spec}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
