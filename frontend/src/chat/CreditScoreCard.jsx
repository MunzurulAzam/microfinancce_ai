import { useState } from 'react';
import { Shield } from 'lucide-react';
import '../components/Ask/ChatInterface.css';
export default function CreditScoreCard({ data }) {
        if (!data) return null;

        const { percentage, classification, total_score, max_score,
            client_scoring, branch_scoring, lo_scoring,
            member_name, member_code, ai_analysis } = data;

        const classColor = {
            'Excellent': '#059669',
            'Good': '#2563EB',
            'Moderate Risk': '#D97706',
            'High Risk': '#DC2626'
        };

        const classEmoji = {
            'Excellent': '🟢',
            'Good': '🔵',
            'Moderate Risk': '🟡',
            'High Risk': '🔴'
        };

        const color = classColor[classification] || '#6B7280';

        return (
            <div className="score-card">
                
                <div className="score-card-header">
                    <div className="score-card-title">
                        <Shield size={20} />
                        <span>Credit Score Report</span>
                    </div>
                    <div className="score-card-client">
                        {member_name} <span className="member-code">{member_code}</span>
                    </div>
                </div>

                <div className="score-gauge-section">
                    <div className="score-gauge" style={{ '--score-color': color }}>
                        <svg viewBox="0 0 120 120" className="gauge-svg">
                            <circle cx="60" cy="60" r="52" className="gauge-bg" />
                            <circle cx="60" cy="60" r="52" className="gauge-fill"
                                style={{
                                    strokeDasharray: `${(percentage / 100) * 326.73} 326.73`,
                                    stroke: color
                                }}
                            />
                        </svg>
                        <div className="gauge-text">
                            <span className="gauge-percent" style={{ color }}>{percentage}%</span>
                            <span className="gauge-label">Score</span>
                        </div>
                    </div>
                    <div className="score-classification" style={{ background: `${color}15`, color, borderColor: `${color}40` }}>
                        {classEmoji[classification]} {classification}
                    </div>
                    <div className="score-total">{total_score} / {max_score} points</div>
                </div>

                <div className="score-categories">
                    {[
                        { label: '📋 Client Scoring', data: client_scoring },
                        { label: '🏢 Branch Performance', data: branch_scoring, sub: branch_scoring?.branch_name },
                        { label: '👤 Loan Officer', data: lo_scoring, sub: lo_scoring?.lo_name },
                    ].map((cat, idx) => (
                        <ScoreCategory key={idx} label={cat.label} catData={cat.data} sub={cat.sub} />
                    ))}
                </div>

                {ai_analysis && (
                    <div className="score-ai-section">
                        <div className="score-ai-header">AI Analysis</div>
                        <div className="score-ai-text">{ai_analysis}</div>
                    </div>
                )}
            </div>
        );
    };
const ScoreCategory = ({ label, catData, sub }) => {
    const [expanded, setExpanded] = useState(false);
    if (!catData) return null;

    const { score, max, percentage, details } = catData;

    return (
        <div className="score-cat">
            <div className="score-cat-header" onClick={() => setExpanded(!expanded)}>
                <div className="score-cat-label">
                    <span>{label}</span>
                    {sub && sub !== 'N/A' && <span className="score-cat-sub">{sub}</span>}
                </div>
                <div className="score-cat-right">
                    <div className="score-cat-bar-bg">
                        <div className="score-cat-bar-fill" style={{ width: `${percentage}%` }} />
                    </div>
                    <span className="score-cat-pct">{score}/{max} ({percentage}%)</span>
                    <span className={`score-cat-arrow ${expanded ? 'expanded' : ''}`}>▸</span>
                </div>
            </div>
            {expanded && details && (
                <div className="score-cat-details">
                    {details.map((d, i) => (
                        <div key={i} className="score-detail-row">
                            <div className="score-detail-dots">
                                {[1, 2, 3, 4, 5].map(n => (
                                    <span key={n} className={`score-dot ${n <= d.score ? 'filled' : ''}`} />
                                ))}
                            </div>
                            <span className="score-detail-name">{d.parameter}</span>
                            <span className="score-detail-reason">{d.reason}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

