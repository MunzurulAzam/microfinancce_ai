import { Link, useLocation } from 'react-router-dom';
import { Bot, Upload, BarChart3, Users, AlertTriangle } from 'lucide-react';
import './Header.css';

const Header = () => {
    const location = useLocation();

    const navItems = [
        { path: '/', label: 'Ask AI', icon: Bot },
        { path: '/upload', label: 'Upload', icon: Upload },
        { path: '/dashboard', label: 'Dashboard', icon: BarChart3 },
        { path: '/clients', label: 'Clients', icon: Users },
        { path: '/risk', label: 'Risk', icon: AlertTriangle },
    ];

    return (
        <header className="header">
            <div className="header-container">
                <div className="header-brand">
                    <div className="brand-icon">
                        <Bot size={28} />
                    </div>
                    <h1 className="brand-title">Microfinance AI</h1>
                </div>

                <nav className="header-nav">
                    {navItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = location.pathname === item.path;

                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`nav-item ${isActive ? 'nav-item-active' : ''}`.trim()}
                            >
                                <Icon size={18} />
                                <span>{item.label}</span>
                            </Link>
                        );
                    })}
                </nav>
            </div>
        </header>
    );
};

export default Header;
