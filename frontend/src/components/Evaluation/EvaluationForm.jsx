import React, { useState } from 'react';
import { User, Briefcase, Calendar, DollarSign, Home, Upload, FileText, CheckCircle, AlertCircle, Loader2, FileCheck } from 'lucide-react';
import './EvaluationForm.css';

const EvaluationForm = () => {
    const [formData, setFormData] = useState({
        applicantName: '',
        businessType: 'Retail',
        businessAge: '',
        monthlyIncome: '',
        rentAmount: ''
    });
    const [file, setFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile && selectedFile.type === 'application/pdf') {
            setFile(selectedFile);
            setError(null);
        } else {
            setFile(null);
            setError('Please upload a valid PDF file.');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!file) {
            setError('Please upload a bank statement.');
            return;
        }

        setLoading(true);
        setError(null);
        setResult(null);

        const data = new FormData();
        Object.keys(formData).forEach(key => data.append(key, formData[key]));
        data.append('bankStatement', file);

        try {
            const response = await fetch('http://localhost:5000/api/evaluate', {
                method: 'POST',
                body: data,
            });

            const resData = await response.json();
            if (resData.success) {
                setResult(resData.data);
            } else {
                setError(resData.error || 'Something went wrong');
            }
        } catch (err) {
            setError('Failed to connect to the server');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="evaluation-container">
            <div className="evaluation-card glass">
                <div className="evaluation-header">
                    <h2>Applicant Evaluation</h2>
                    <p>Enter applicant details and upload statements for AI-powered verification.</p>
                </div>

                <form onSubmit={handleSubmit} className="evaluation-form">
                    <div className="section-title">
                        <FileText size={18} />
                        <span>Section A: Manual Input</span>
                    </div>

                    <div className="form-grid">
                        <div className="input-group">
                            <label><User size={16} /> Applicant Name</label>
                            <input
                                type="text"
                                name="applicantName"
                                value={formData.applicantName}
                                onChange={handleInputChange}
                                required
                                placeholder="Full Name"
                            />
                        </div>

                        <div className="input-group">
                            <label><Briefcase size={16} /> Business Type</label>
                            <select name="businessType" value={formData.businessType} onChange={handleInputChange}>
                                <option value="Retail">Retail</option>
                                <option value="Manufacturing">Manufacturing</option>
                                <option value="Service">Service</option>
                            </select>
                        </div>

                        <div className="input-group">
                            <label><Calendar size={16} /> Business Age (Years)</label>
                            <input
                                type="number"
                                name="businessAge"
                                value={formData.businessAge}
                                onChange={handleInputChange}
                                required
                                placeholder="e.g. 5"
                            />
                        </div>

                        <div className="input-group">
                            <label><DollarSign size={16} /> Monthly Income</label>
                            <input
                                type="number"
                                name="monthlyIncome"
                                value={formData.monthlyIncome}
                                onChange={handleInputChange}
                                required
                                placeholder="Total per month"
                            />
                        </div>

                        <div className="input-group">
                            <label><Home size={16} /> Shop/Office Rent</label>
                            <input
                                type="number"
                                name="rentAmount"
                                value={formData.rentAmount}
                                onChange={handleInputChange}
                                required
                                placeholder="Monthly rent"
                            />
                        </div>
                    </div>

                    <div className="section-title mt-6">
                        <Upload size={18} />
                        <span>Section B: Document Upload</span>
                    </div>

                    <div className={`file-upload-zone ${file ? 'has-file' : ''}`}>
                        <input
                            type="file"
                            id="statement-upload"
                            accept=".pdf"
                            onChange={handleFileChange}
                            style={{ display: 'none' }}
                        />
                        <label htmlFor="statement-upload" className="upload-label">
                            {file ? (
                                <div className="file-info">
                                    <CheckCircle size={32} className="text-success" />
                                    <span>{file.name}</span>
                                    <button type="button" onClick={() => setFile(null)} className="btn-change">Change</button>
                                </div>
                            ) : (
                                <div className="upload-placeholder">
                                    <Upload size={32} />
                                    <span>Upload Bank/Transaction PDF Statement</span>
                                    <p>Only PDF files are supported</p>
                                </div>
                            )}
                        </label>
                    </div>

                    {error && (
                        <div className="error-message">
                            <AlertCircle size={18} />
                            <span>{error}</span>
                        </div>
                    )}

                    <button type="submit" className="btn-submit" disabled={loading}>
                        {loading ? <><Loader2 className="animate-spin" size={18} /> Processing...</> : 'Evaluate Application'}
                    </button>
                </form>

                {result && (
                    <div className="result-section glass-dark fade-in">
                        <h3>Evaluation Results</h3>

                        <div className="status-badge" data-status={result.validation.status}>
                            {result.validation.status === 'Verified' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                            {result.validation.status}
                        </div>

                        <div className="metrics-grid">
                            <div className="metric-item">
                                <span className="m-label">Total Credit Sum</span>
                                <span className="m-value">৳ {result.metrics.totalCredit.toLocaleString()}</span>
                            </div>
                            <div className="metric-item">
                                <span className="m-label">Total Debit Sum</span>
                                <span className="m-value">৳ {result.metrics.totalDebit.toLocaleString()}</span>
                            </div>
                            <div className="metric-item">
                                <span className="m-label">Avg. Monthly Balance</span>
                                <span className="m-value">৳ {result.metrics.averageMonthlyBalance.toLocaleString()}</span>
                            </div>
                        </div>

                        <div className="loan-prediction-card glass-light">
                            <div className="prediction-header">
                                <FileCheck size={20} className="text-primary" />
                                <h4>Loan Eligibility Analysis</h4>
                            </div>
                            <div className="prediction-content">
                                {result.loanPrediction.isEligible ? (
                                    <div className="eligibility-details">
                                        <div className="eligibility-status success">
                                            <CheckCircle size={24} />
                                            <div>
                                                <strong>Eligible for Loan</strong>
                                                <p>{result.loanPrediction.reason}</p>
                                            </div>
                                        </div>
                                        <div className="suggested-amount">
                                            <span>Suggested Loan Amount</span>
                                            <h2>৳ {result.loanPrediction.suggestedAmount.toLocaleString()}</h2>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="eligibility-status warning">
                                        <AlertCircle size={24} />
                                        <div>
                                            <strong>Not Eligible / Manual Review Required</strong>
                                            <p>{result.loanPrediction.reason}</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="validation-msg">
                            <p>{result.validation.message}</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default EvaluationForm;
