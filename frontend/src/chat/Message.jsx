import { PeriodChoices } from './ReportPeriods';
import GroupReport from '../components/AskWarehouse/GroupReport';
import CreditScoreCard from './CreditScoreCard';
import { MemberAnalysisCard, ResultTable } from './DataCards';

export default function Message({ message: m, onRetry, onRegenerate, busy }) {
    const r = m.response || {};
    return <article className={`cw-message cw-${m.role}`}>
        <div className="cw-speaker">{m.role === 'user' ? 'You' : 'UMOJA AI'} <time>{new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></div>
        {m.status === 'pending' ? <p role="status" className="cw-pending">Preparing your response…</p> : <>
            {r.resolved_question && r.resolved_question !== m.question && <details className="cw-resolved"><summary>Interpreted question</summary>{r.resolved_question}</details>}
            {r.report ? <GroupReport report={r.report} onRegenerate={() => onRegenerate(`Group Performance Report ${r.report.period}`, r.report.country)} />
                : r.credit_score && r.data ? <CreditScoreCard data={r.data} />
                : r.mode === 'member_analysis' ? <MemberAnalysisCard r={r} />
                : <><div className="cw-text">{m.text}</div>
                    {r.sql && <details><summary>View SQL</summary><pre className="wq-sql">{r.sql}</pre></details>}
                    <ResultTable columns={r.columns} rows={r.rows} count={r.row_count} truncated={r.truncated} />
                </>}
            {r.country_enforced === false && <p role="alert">Country scope could not be confirmed. Check the SQL.</p>}
            {r.available_periods && <PeriodChoices periods={r.available_periods} busy={busy} onSelect={text => onRegenerate(text, r.country || m.country)}/> }
            {r.availability_error && <p>Available months could not be checked because the warehouse is unavailable.</p>}
            {r.retryable === false && r.code?.startsWith('cloud_') && <p>Server AI setup needs attention. Contact the administrator; retry after configuration is corrected.</p>}
            {['error','interrupted'].includes(m.status) && r.retryable !== false && <button type="button" disabled={busy} onClick={() => onRetry(m)}>Retry response</button>}
        </>}
    </article>;
}
