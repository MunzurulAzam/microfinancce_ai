import { useState } from 'react';
import { Download, AlertCircle } from 'lucide-react';
import { downloadGroupReport } from '../../services/api';
import './GroupReport.css';

const colors = ['#133e88', '#00a953', '#ce281f', '#e6a300'];
const number = value => value == null ? 'Unavailable' : value.toLocaleString('en-US', { maximumFractionDigits: 2 });

function ReportChart({ countries, field, title }) {
    const values = countries.map(c => c[field]).filter(v => v != null);
    const min = Math.min(0, ...values), max = Math.max(0, ...values);
    const span = max - min || 1;
    const y = value => 150 - (value - min) / span * 110;
    return <figure className="gr-chart">
        <figcaption>{title}</figcaption>
        {!values.length ? <p>Unavailable — see source notes</p> : <svg viewBox="0 0 400 200" role="img" aria-label={title}>
            <line x1="15" x2="390" y1={y(0)} y2={y(0)} stroke="#ccd3df" />
            {countries.map((c, i) => {
                const x = 25 + i * 370 / countries.length;
                return <g key={c.country}>
                    {c[field] != null && <rect x={x} y={Math.min(y(c[field]), y(0))} width={370 / countries.length - 25}
                        height={Math.abs(y(c[field]) - y(0))} fill={colors[i % colors.length]} />}
                    <text x={x} y="172">{c.name}</text><text x={x} y="192">{number(c[field])}{c[field] != null && '%'}</text>
                </g>;
            })}
        </svg>}
    </figure>;
}

export default function GroupReport({ report, onRegenerate }) {
    const [downloading, setDownloading] = useState(false);
    const [error, setError] = useState('');
    const download = async () => {
        setDownloading(true); setError('');
        try {
            const blob = await downloadGroupReport(report.report_id);
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url; anchor.download = `Group Performance Report - ${report.period_label}.pdf`;
            document.body.appendChild(anchor); anchor.click(); anchor.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (e) { setError(e.response?.status === 404 ? 'This saved PDF snapshot is no longer available. Generate a new report to get a new PDF; this preview will stay unchanged.' : 'PDF download failed. Please retry.'); }
        finally { setDownloading(false); }
    };
    const labels = [['Countries', 'countries'], ['Branches with portfolio', 'branches'], ['Reported borrowers', 'borrowers'],
        ['Group principal portfolio (USD)', 'principal_usd'], ['Group PAR >30 (%)', 'par_percent'], ['Portfolio at risk (USD)', 'par_amount_usd']];
    return <article className="group-report">
        <div className="gr-toolbar"><span>Monthly management report</span>
            <button onClick={download} disabled={downloading}><Download size={16} />{downloading ? 'Preparing PDF…' : 'Download PDF'}</button></div>
        {error && <p role="alert" className="gr-warning">{error}{onRegenerate && error.includes('snapshot') && <button onClick={onRegenerate}>Prepare new report question</button>}</p>}
        <header className="gr-cover"><p className="gr-brand">UMOJA <span>INTERNATIONAL</span></p>
            <div className="gr-title"><h2>END OF MONTH<br />REPORT</h2><p>{report.period_label} | Comparative review against {report.comparison_label}</p></div>
            <div className="gr-kpis">{labels.map(([label, key]) => <div key={key}><strong>{number(report.metrics[key])}</strong><span>{label}</span></div>)}</div>
            <p className="gr-tagline">Monthly portfolio, country performance and branch risk review</p>
        </header>
        {report.availability.warnings.length > 0 && <p className="gr-warning"><AlertCircle size={18} /> Some metrics are unavailable or could not be reconciled. See source notes below.</p>}
        {report.sections.map(section => <section key={section.id} className="gr-section">
            <h3>{section.title}</h3>
            {section.paragraphs?.map((p, i) => <p key={i}>{p}</p>)}
            {section.id === 'executive' && <div className="gr-charts">
                <ReportChart countries={report.countries} field="growth_percent" title="Portfolio Growth (local currency)" />
                <ReportChart countries={report.countries} field="portfolio_share_percent" title="Portfolio Share (USD)" />
            </div>}
            {section.blocks?.map((b, i) => <div key={i}><h4>{b.heading}</h4><p>{b.text}</p></div>)}
            {section.table && <div className="gr-table-scroll"><table><thead><tr>{section.table.columns.map(c => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{section.table.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>}
        </section>)}
        <details className="gr-sources"><summary>Sources and availability ({report.availability.warnings.length} notes)</summary>
            {report.sources.map((s, i) => <p key={i}><strong>{s.table}: </strong>{s.basis}</p>)}
            <ul>{report.availability.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
            <p>Report ID: {report.report_id} · Generated: {report.generated_at}</p>
        </details>
    </article>;
}
