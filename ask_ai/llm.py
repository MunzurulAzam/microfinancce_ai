from core.cloud import generate as cloud_generate

def generate(prompt, **kwargs):
    return cloud_generate(prompt, task="sql", **kwargs)


def summarize(question, columns, rows, *, timeout=60):
    """ natural-language phrasing of a result set."""
    result = generate(
        "Answer the user's question in ONE short sentence using the data.\n"
        "Use the numbers exactly as given; do not recalculate or round them.\n"
        f"Question: {question}\n"
        f"Columns: {columns}\n"
        f"Rows: {rows[:20]}\n"
        "Answer:",
        temperature=0.2,
        num_predict=120,
        timeout=timeout,
    )
    return result['text'].strip() if result['success'] and result['text'] else None
