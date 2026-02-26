import { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, BarChart3, TrendingUp, AlertCircle, Shield } from 'lucide-react';
import { askQuestion } from '../../services/api';
import Button from '../Common/Button';
import Card from '../Common/Card';
import './ChatInterface.css';

const ChatInterface = () => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(scrollToBottom, [messages]);

    useEffect(() => {
        // Welcome message
        setMessages([{
            type: 'ai',
            content: 'Hello! I can help you analyze your microfinance data. Ask me anything!\n\nExamples:\n• Credit score for [client name]\n• Show me statistics\n• Analyze client John Doe\n• Show top clients\n• Risk analysis',
            timestamp: new Date()
        }]);
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage = {
            type: 'user',
            content: input,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setLoading(true);

        try {
            const response = await askQuestion(input);

            const aiMessage = {
                type: 'ai',
                content: response.answer,
                intent: response.intent,
                data: response.data,
                creditScore: response.credit_score || false,
                timestamp: new Date()
            };

            setMessages(prev => [...prev, aiMessage]);
        } catch (error) {
            const errorMessage = {
                type: 'error',
                content: error.error || 'Failed to get response. Please try again.',
                timestamp: new Date()
            };

            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    };

    const quickActions = [
        { label: 'Credit Score', question: 'Credit score for ', icon: Shield, autoFocus: true },
        { label: 'Show Statistics', question: 'Show me statistics', icon: BarChart3 },
        { label: 'Quick Insights', question: 'Show insights', icon: Sparkles },
        { label: 'Top Clients', question: 'Show top clients', icon: TrendingUp },
        { label: 'Risk Analysis', question: 'Show risk analysis', icon: AlertCircle },
    ];

    const handleQuickAction = (action) => {
        setInput(action.question);
    };

    // ── Rich score card rendering ──
    const renderScoreCard = (data) => {
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
                {/* Header */}
                <div className="score-card-header">
                    <div className="score-card-title">
                        <Shield size={20} />
                        <span>Credit Score Report</span>
                    </div>
                    <div className="score-card-client">
                        {member_name} <span className="member-code">{member_code}</span>
                    </div>
                </div>

                {/* Gauge */}
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

                {/* Category Breakdown */}
                <div className="score-categories">
                    {[
                        { label: '📋 Client Scoring', data: client_scoring },
                        { label: '🏢 Branch Performance', data: branch_scoring, sub: branch_scoring?.branch_name },
                        { label: '👤 Loan Officer', data: lo_scoring, sub: lo_scoring?.lo_name },
                    ].map((cat, idx) => (
                        <ScoreCategory key={idx} label={cat.label} catData={cat.data} sub={cat.sub} />
                    ))}
                </div>

                {/* AI Analysis */}
                {ai_analysis && (
                    <div className="score-ai-section">
                        <div className="score-ai-header">🤖 AI Analysis</div>
                        <div className="score-ai-text">{ai_analysis}</div>
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="chat-container">
            <div className="chat-header">
                <div className="chat-header-content">
                    <Sparkles className="chat-icon" size={24} />
                    <div>
                        <h1 className="chat-title">Ask AI Anything</h1>
                        <p className="chat-subtitle">Get instant insights about your microfinance portfolio</p>
                    </div>
                </div>
            </div>

            <div className="chat-messages">
                {messages.map((message, index) => (
                    <div key={index} className={`message message-${message.type}`}>
                        <div className="message-bubble">
                            {message.creditScore && message.data ? (
                                renderScoreCard(message.data)
                            ) : (
                                <pre className="message-content">{message.content}</pre>
                            )}
                            <span className="message-time">
                                {message.timestamp.toLocaleTimeString('en-US', {
                                    hour: '2-digit',
                                    minute: '2-digit'
                                })}
                            </span>
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="message message-ai">
                        <div className="message-bubble message-loading">
                            <div className="typing-indicator">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
                <div className="quick-actions">
                    {quickActions.map((action, index) => {
                        const Icon = action.icon;
                        return (
                            <button
                                key={index}
                                className="quick-action-btn"
                                onClick={() => handleQuickAction(action)}
                                disabled={loading}
                            >
                                <Icon size={16} />
                                <span>{action.label}</span>
                            </button>
                        );
                    })}
                </div>

                <form onSubmit={handleSubmit} className="chat-form">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask me anything about your microfinance data..."
                        className="chat-input"
                        disabled={loading}
                    />
                    <Button
                        type="submit"
                        disabled={!input.trim() || loading}
                        loading={loading}
                        className="send-btn"
                    >
                        <Send size={18} />
                    </Button>
                </form>
            </div>
        </div>
    );
};


// ── Score Category Component ──
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

export default ChatInterface;
