import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import ChatInterface from './components/Ask/ChatInterface';
import FileUpload from './components/Upload/FileUpload';
import Dashboard from './components/Dashboard/Dashboard';
import EvaluationForm from './components/Evaluation/EvaluationForm';
import './styles/globals.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<ChatInterface />} />
          <Route path="upload" element={<FileUpload />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="evaluation" element={<EvaluationForm />} />
          <Route path="clients" element={<ComingSoon page="Clients" />} />
          <Route path="risk" element={<ComingSoon page="Risk Analysis" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

// Placeholder for coming soon pages
function ComingSoon({ page }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '400px',
      flexDirection: 'column',
      gap: '1rem'
    }}>
      <h2 style={{ fontSize: '1.5rem', fontWeight: '700' }}>{page}</h2>
      <p style={{ color: 'var(--text-secondary)' }}>
        This feature is coming soon! For now, use the Ask AI page to get this information.
      </p>
    </div>
  );
}

export default App;
