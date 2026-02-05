import { useState, useEffect } from 'react';
import { Users, TrendingUp, DollarSign, AlertTriangle } from 'lucide-react';
import { getStats, getTopClients, getRiskAnalysis } from '../../services/api';
import Card from '../Common/Card';
import Loading from '../Common/Loading';
import './Dashboard.css';

const Dashboard = () => {
    const [stats, setStats] = useState(null);
    const [topClients, setTopClients] = useState([]);
    const [riskData, setRiskData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            const [statsData, clientsData, risk] = await Promise.all([
                getStats(),
                getTopClients(5),
                getRiskAnalysis()
            ]);

            setStats(statsData);
            setTopClients(clientsData);
            setRiskData(risk);
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <Loading fullScreen />;
    }

    if (!stats) {
        return (
            <div className="empty-state">
                <p>No data available. Please upload a CSV file in the Upload page to start analysis.</p>
                <p className="empty-state-hint">The system will automatically load the default dataset if available on server startup.</p>
            </div>
        );
    }

    return (
        <div className="dashboard-container">
            <div className="dashboard-header">
                <h1 className="dashboard-title">Dashboard</h1>
                <p className="dashboard-subtitle">Overview of your microfinance portfolio</p>
            </div>

            <div className="stats-cards">
                <Card className="stat-card">
                    <div className="stat-icon" style={{ background: 'rgba(102, 126, 234, 0.2)' }}>
                        <Users size={24} color="#667eea" />
                    </div>
                    <div className="stat-content">
                        <p className="stat-label">Total Clients</p>
                        <h3 className="stat-number">{stats.total_clients}</h3>
                    </div>
                </Card>

                <Card className="stat-card">
                    <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.2)' }}>
                        <TrendingUp size={24} color="#10b981" />
                    </div>
                    <div className="stat-content">
                        <p className="stat-label">Avg Performance</p>
                        <h3 className="stat-number">{stats.average_client_score?.toFixed(1)}/100</h3>
                    </div>
                </Card>

                <Card className="stat-card">
                    <div className="stat-icon" style={{ background: 'rgba(79, 172, 254, 0.2)' }}>
                        <DollarSign size={24} color="#4facfe" />
                    </div>
                    <div className="stat-content">
                        <p className="stat-label">Total Portfolio</p>
                        <h3 className="stat-number">
                            {(stats.total_loan_portfolio / 1000000).toFixed(1)}M UGX
                        </h3>
                    </div>
                </Card>

                <Card className="stat-card">
                    <div className="stat-icon" style={{ background: 'rgba(239, 68, 68, 0.2)' }}>
                        <AlertTriangle size={24} color="#ef4444" />
                    </div>
                    <div className="stat-content">
                        <p className="stat-label">Clients with Overdue</p>
                        <h3 className="stat-number">{stats.clients_with_overdue}</h3>
                    </div>
                </Card>
            </div>

            <div className="dashboard-grid">
                <Card className="dashboard-card">
                    <h2 className="card-title">Top Performers</h2>
                    <div className="top-clients-list">
                        {topClients.map((client, index) => (
                            <div key={index} className="top-client-item">
                                <div className="rank-badge">#{index + 1}</div>
                                <div className="client-info">
                                    <p className="client-name">{client.name}</p>
                                    <p className="client-detail">Score: {client.score}/100</p>
                                </div>
                                <div className="client-amount">
                                    {(client.loan_amount / 1000).toFixed(0)}K UGX
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>

                {riskData && (
                    <Card className="dashboard-card">
                        <h2 className="card-title">Risk Analysis</h2>
                        <div className="risk-summary">
                            <div className="risk-stat">
                                <p className="risk-label">High Risk Clients</p>
                                <p className="risk-value danger">{riskData.total_high_risk}</p>
                            </div>
                            <div className="risk-stat">
                                <p className="risk-label">At Risk Amount</p>
                                <p className="risk-value">
                                    {(riskData.total_at_risk_amount / 1000000).toFixed(2)}M UGX
                                </p>
                            </div>
                        </div>
                    </Card>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
