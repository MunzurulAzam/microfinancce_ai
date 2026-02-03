import { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, BarChart3, TrendingUp, AlertCircle } from 'lucide-react';
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
            content: 'Hello! I can help you analyze your microfinance data. Ask me anything!\n\nExamples:\n• Show me statistics\n• Analyze client John Doe\n• Show top clients\n• Risk analysis',
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
        { label: 'Show Statistics', question: 'Show me statistics', icon: BarChart3 },
        { label: 'Quick Insights', question: 'Show insights', icon: Sparkles },
        { label: 'Top Clients', question: 'Show top clients', icon: TrendingUp },
        { label: 'Risk Analysis', question: 'Show risk analysis', icon: AlertCircle },
    ];

    const handleQuickAction = (question) => {
        setInput(question);
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
                            <pre className="message-content">{message.content}</pre>
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
                                onClick={() => handleQuickAction(action.question)}
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

export default ChatInterface;
