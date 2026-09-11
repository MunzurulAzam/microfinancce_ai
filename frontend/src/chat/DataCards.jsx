import { AlertCircle, CheckCircle2, XCircle, Database, Lightbulb } from 'lucide-react';
import '../components/AskWarehouse/AskWarehouse.css';
const isNumeric = (v) => typeof v === 'number' || (v !== '' && v !== null && !isNaN(v));

const formatCell = (v) => {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(v);
};

const CLASS_COLOR = {
    Excellent: '#059669', Good: '#2563EB',
    'Moderate Risk': '#D97706', 'High Risk': '#DC2626',
};
const DECISION_STYLE = {
    Approve: { color: '#059669', Icon: CheckCircle2 },
    'Conditional Approve': { color: '#D97706', Icon: AlertCircle },
    Reject: { color: '#DC2626', Icon: XCircle },
};

export const MemberAnalysisCard = ({ r }) => {
    const color = CLASS_COLOR[r.classification] || '#6B7280';
    const dec = DECISION_STYLE[r.decision] || { color: '#6B7280', Icon: AlertCircle };
    const DIcon = dec.Icon;
    const fmt = (n) => (n || n === 0) ? Number(n).toLocaleString() : '—';

    return (
        <div className="ma-card">
            
            <div className="ma-head">
                <div>
                    <div className="ma-name">{r.member?.name}</div>
                    <div className="ma-sub">
                        {r.member?.code} · {r.member?.country} · {r.member?.branch} · {r.member?.loan_officer}
                    </div>
                </div>
                <div className="ma-decision" style={{ color: dec.color, borderColor: `${dec.color}55`, background: `${dec.color}12` }}>
                    <DIcon size={18} /> {r.decision}
                </div>
            </div>

            <div className="ma-stats">
                <div className="ma-stat">
                    <span className="ma-stat-label">Credit Score</span>
                    <span className="ma-stat-value" style={{ color }}>{r.score}%</span>
                    <span className="ma-badge" style={{ color, background: `${color}15`, borderColor: `${color}40` }}>{r.classification}</span>
                </div>
                <div className="ma-stat">
                    <span className="ma-stat-label">Suggested Loan Amount</span>
                    <span className="ma-stat-value">{fmt(r.recommended_loan_amount)}</span>
                    <span className="ma-stat-note">{r.amount_reasoning}</span>
                </div>
                <div className="ma-stat">
                    <span className="ma-stat-label">Condition</span>
                    <span className="ma-stat-value ma-cond">{r.condition_summary}</span>
                </div>
            </div>

            {r.analysis && (
                <div className="ma-analysis">
                    <div className="ma-analysis-head"><Database size={15} /> Analysis</div>
                    <p>{r.analysis}</p>
                </div>
            )}

            {r.suggestions?.length > 0 && (
                <div className="ma-suggest">
                    <div className="ma-analysis-head"><Lightbulb size={15} /> Suggestions</div>
                    <ul>{r.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
            )}

            {/* Member codes repeat across countries — never let the reader assume the person. */}
            {r.match_note && (
                <div className="ma-note">
                    <AlertCircle size={14} /> {r.match_note}
                </div>
            )}

            {r.other_matches?.length > 0 && (
                <div className="ma-others">Other matches: {r.other_matches.join(' · ')}</div>
            )}
        </div>
    );
};

export const ResultTable = ({ columns, rows, count, truncated }) => {
    if (!columns || columns.length === 0) return null;
    if (!rows || rows.length === 0) {
        return <div className="wq-empty">Query ran successfully but returned no rows.</div>;
    }

    return (
        <div className="wq-table-wrap">
            <div className="wq-table-meta">
                {count} row{count === 1 ? '' : 's'}
                {truncated && ' (capped — narrow the question for the full set)'}
            </div>
            <div className="wq-table-scroll">
                <table className="wq-table">
                    <thead>
                        <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
                    </thead>
                    <tbody>
                        {rows.map((row, i) => (
                            <tr key={i}>
                                {columns.map((c) => (
                                    <td key={c} className={isNumeric(row[c]) ? 'wq-num' : ''}>
                                        {formatCell(row[c])}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

