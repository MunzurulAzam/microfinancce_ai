import { Link, useLocation } from 'react-router-dom';
import { Bot, Upload, BarChart3, Users, AlertTriangle, FileCheck, ShieldCheck, ScanLine, Database } from 'lucide-react';
import './Header.css';

const Header = () => {
    const location = useLocation();

    const navItems = [
        { path: '/', label: 'Ask AI', icon: Bot },
        { path: '/ask-ai', label: 'Data Q&A', icon: Database },
        { path: '/evaluation', label: 'Evaluation', icon: FileCheck },
        { path: '/verify', label: 'Verify Doc', icon: ShieldCheck },
        { path: '/scan-id', label: 'Scan ID', icon: ScanLine },
        { path: '/upload', label: 'Upload', icon: Upload },
        
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
