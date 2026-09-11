import { useState } from 'react';
import { getReportPeriods } from '../services/api';

export function PeriodChoices({ periods, onSelect, busy }) {
    if (!periods?.length) return <p>No historical month-end snapshots are available for this country selection.</p>;
    return <div className="cw-period-choices">{periods.map(p => <button type="button" key={p.period} disabled={busy} onClick={() => onSelect(`Group Performance Report ${p.period}`)}>
        {p.period}{p.coverage === 'partial' ? ` · Missing: ${p.missing_countries.join(', ')}` : ''}
    </button>)}</div>;
}
export default function ReportPeriods({ country, onSelect, busy }) {
    const [result,setResult] = useState(null), [error,setError] = useState(''), [loading,setLoading] = useState(false);
    async function load() {
        setLoading(true); setError(''); setResult(null);
        try { setResult(await getReportPeriods(country)); }
        catch(e) { setError(e.error || 'Available months could not be checked. Please retry.'); }
        finally { setLoading(false); }
    }
    return <details className="cw-periods"><summary>Available report months</summary>
        <button type="button" onClick={load} disabled={loading}>{loading ? 'Checking…' : 'Check warehouse months'}</button>
        {error && <p role="alert">{error}</p>}
        {result && <><PeriodChoices periods={result.periods} busy={busy} onSelect={onSelect}/><p>Country coverage may be partial. Selecting a month prepares a new question.</p></>}
    </details>;
}
