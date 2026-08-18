import { useState } from 'react';
import { Send, Database, Code2, ChevronDown, AlertCircle, Globe, CheckCircle2, XCircle, Lightbulb } from 'lucide-react';
import { askWarehouse } from '../../services/api';
import Button from '../Common/Button';
import './AskWarehouse.css';

// Country chips — "All" means no country filter (combined across all 4 countries).
const COUNTRIES = [
    { code: 'ALL', label: 'All countries', flag: '🌍' },
    { code: 'UG', label: 'Uganda', flag: '🇺🇬' },
    { code: 'KY', label: 'Kenya', flag: '🇰🇪' },
    { code: 'ZM', label: 'Zambia', flag: '🇿🇲' },
    { code: 'TZ', label: 'Tanzania', flag: '🇹🇿' },
];

const EXAMPLES = [
    'Total loan portfolio across all countries?',
    'How many active members in each country?',
    'Top 5 branches by active loan portfolio',
    'How many clients have overdue payments?',
    'Average loan size for female members',
];

const isNumeric = (v) => typeof v === 'number' || (v !== '' && v !== null && !isNaN(v));

const formatCell = (v) => {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(v);
};

const AskWarehouse = () => {
    const [input, setInput] = useState('');
    const [country, setCountry] = useState('ALL');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [showSql, setShowSql] = useState(false);

    const submit = async (e) => {
        e?.preventDefault();
        if (!input.trim() || loading) return;

        setLoading(true);
        setError(null);
        setResult(null);
        setShowSql(false);

        try {
            // The country chip is enforced server-side as a real CountryCode
            // filter, so the question text is sent exactly as typed.
            const data = await askWarehouse(input.trim(), {
                country: country === 'ALL' ? null : country,
            });
            if (data.success) {
                setResult(data);
            } else {
                setError({
                    message: data.error || 'Could not answer that question.',
                    sql: data.sql,
                    suggestions: data.suggestions,
                });
            }
        } catch (err) {
            setError({ message: err.error || err.message || 'Request failed. Is the backend running?' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="wq-container">
            {/* Header */}
            <div className="wq-header">
                <div className="wq-header-icon"><Database size={24} /></div>
                <div>
                    <h1 className="wq-title">Data Q&amp;A</h1>
                    <p className="wq-subtitle">
                        Ask anything across the 4-country warehouse (UG · KY · ZM · TZ). Answers come
                        straight from your data — no guessing.
                    </p>
                </div>
            </div>

            {/* Form */}
            <form onSubmit={submit} className="wq-form">
                <div className="wq-input-row">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="e.g. Total loan portfolio across all countries?"
                        className="wq-input"
                        disabled={loading}
                    />
                    <Button type="submit" disabled={!input.trim() || loading} loading={loading} className="wq-send">
                        <Send size={18} />
                    </Button>
                </div>

                {/* Country chips */}
                <div className="wq-chips">
                    <Globe size={15} className="wq-chips-icon" />
                    {COUNTRIES.map((c) => (
                        <button
                            key={c.code}
                            type="button"
                            className={`wq-chip ${country === c.code ? 'wq-chip-active' : ''}`}
                            onClick={() => setCountry(c.code)}
                            disabled={loading}
                        >
                            <span>{c.flag}</span> {c.code === 'ALL' ? 'All' : c.code}
                        </button>
                    ))}
                </div>
            </form>

            {/* Examples (only before first result) */}
            {!result && !error && !loading && (
                <div className="wq-examples">
                    <span className="wq-examples-label">Try:</span>
                    {EXAMPLES.map((ex) => (
                        <button key={ex} className="wq-example" onClick={() => setInput(ex)}>
                            {ex}
                        </button>
                    ))}
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="wq-loading">
                    <div className="wq-typing"><span /><span /><span /></div>
                    <span>Generating SQL and querying the warehouse…</span>
                </div>
            )}

            {/* Error */}
            {error && !loading && (
                <div className="wq-error">
                    <AlertCircle size={18} />
                    <div>
                        <div className="wq-error-msg">{error.message}</div>
                        {error.suggestions?.length > 0 && (
                            <div className="wq-suggest">
                                Did you mean: {error.suggestions.join(' · ')}
                            </div>
                        )}
                        {error.sql && <pre className="wq-sql wq-error-sql">{error.sql}</pre>}
                    </div>
                </div>
            )}

            {/* Member analysis result */}
            {result && !loading && result.mode === 'member_analysis' && (
                <MemberAnalysisCard r={result} />
            )}

            {/* SQL result */}
            {result && !loading && result.mode !== 'member_analysis' && (
                <div className="wq-result">
                    {result.answer && (
                        <div className="wq-answer">
                            <Database size={16} className="wq-answer-icon" />
                            <p>{result.answer}</p>
                        </div>
                    )}

                    {/* The country chip could not be confirmed in the SQL — say so
                        rather than let the numbers read as scoped when they may not be. */}
                    {result.country_enforced === false && (
                        <div className="ma-note">
                            <AlertCircle size={14} />
                            Could not confirm this query is limited to {result.country} — check the SQL.
                        </div>
                    )}

                    {/* Collapsible SQL */}
                    {result.sql && (
                        <div className="wq-sql-block">
                            <button className="wq-sql-toggle" onClick={() => setShowSql((s) => !s)}>
                                <Code2 size={15} />
                                <span>{showSql ? 'Hide' : 'Show'} SQL</span>
                                <ChevronDown size={15} className={`wq-chevron ${showSql ? 'open' : ''}`} />
                            </button>
                            {showSql && <pre className="wq-sql">{result.sql}</pre>}
                        </div>
                    )}

                    {/* Results table */}
                    <ResultTable
                        columns={result.columns}
                        rows={result.rows}
                        count={result.row_count}
                        truncated={result.truncated}
                    />
                </div>
            )}
        </div>
    );
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

const MemberAnalysisCard = ({ r }) => {
    const color = CLASS_COLOR[r.classification] || '#6B7280';
    const dec = DECISION_STYLE[r.decision] || { color: '#6B7280', Icon: AlertCircle };
    const DIcon = dec.Icon;
    const fmt = (n) => (n || n === 0) ? Number(n).toLocaleString() : '—';

    return (
        <div className="ma-card">
            {/* Header */}
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

            {/* Stat tiles */}
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

            {/* AI analysis */}
            {r.analysis && (
                <div className="ma-analysis">
                    <div className="ma-analysis-head"><Database size={15} /> Analysis</div>
                    <p>{r.analysis}</p>
                </div>
            )}

            {/* Suggestions */}
            {r.suggestions?.length > 0 && (
                <div className="ma-suggest">
                    <div className="ma-analysis-head"><Lightbulb size={15} /> Suggestions</div>
                    <ul>{r.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </div>
            )}

            {/* Member codes repeat across countries — never let the reader assume
                this is the person they meant. */}
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

const ResultTable = ({ columns, rows, count, truncated }) => {
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

export default AskWarehouse;
