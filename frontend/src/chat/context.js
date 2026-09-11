export function contextFor(messages, beforeSequence = Infinity) {
    let context = messages.filter(m => m.sequence < beforeSequence && m.status === 'complete').slice(-6).map(m => ({
        role: m.role,
        text: (m.role === 'user' ? m.text : m.response?.report ? `Group performance report for ${m.response.report.period}` : m.response?.credit_score || m.response?.mode === 'member_analysis' ? 'Member credit analysis returned.' : m.text || '').slice(0, 1500),
        metadata: m.role === 'assistant' ? m.response?.context_metadata || {} : {},
    }));
    while (new TextEncoder().encode(JSON.stringify(context)).length > 13500) context = context.slice(1);
    return context;
}
