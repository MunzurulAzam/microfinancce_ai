import { useState } from 'react';
import { Upload as UploadIcon, FileText, CheckCircle, XCircle } from 'lucide-react';
import { uploadCSV } from '../../services/api';
import Button from '../Common/Button';
import Card from '../Common/Card';
import './FileUpload.css';

const FileUpload = () => {
    const [dragActive, setDragActive] = useState(false);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const droppedFile = e.dataTransfer.files[0];
            if (droppedFile.name.endsWith('.csv') || droppedFile.name.endsWith('.xlsx') || droppedFile.name.endsWith('.xls')) {
                setFile(droppedFile);
                setError(null);
            } else {
                setError('Please upload a CSV or Excel file');
            }
        }
    };

    const handleChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0];
            if (selectedFile.name.endsWith('.csv') || selectedFile.name.endsWith('.xlsx') || selectedFile.name.endsWith('.xls')) {
                setFile(selectedFile);
                setError(null);
            } else {
                setError('Please upload a CSV or Excel file');
            }
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setUploading(true);
        setError(null);
        setResult(null);

        try {
            const response = await uploadCSV(file);
            setResult(response);
            setFile(null);
        } catch (err) {
            setError(err.error || 'Upload failed. Please try again.');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="upload-container">
            <div className="upload-header">
                <h1 className="upload-title">Upload Data</h1>
                <p className="upload-subtitle">
                    Upload your CSV or Excel files to start analyzing
                </p>
            </div>

            <Card className="upload-card">
                <div
                    className={`dropzone ${dragActive ? 'dropzone-active' : ''} ${file ? 'dropzone-has-file' : ''}`.trim()}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                >
                    <input
                        type="file"
                        id="file-upload"
                        className="file-input"
                        onChange={handleChange}
                        accept=".csv, .xlsx, .xls"
                    />

                    <label htmlFor="file-upload" className="dropzone-label">
                        {file ? (
                            <>
                                <FileText size={48} className="dropzone-icon success" />
                                <p className="dropzone-filename">{file.name}</p>
                                <p className="dropzone-filesize">
                                    {(file.size / 1024).toFixed(2)} KB
                                </p>
                            </>
                        ) : (
                            <>
                                <UploadIcon size={48} className="dropzone-icon" />
                                <p className="dropzone-text">
                                    <span className="dropzone-highlight">Click to upload</span> or drag and drop
                                </p>
                                <p className="dropzone-hint">CSV or Excel files only</p>
                            </>
                        )}
                    </label>
                </div>

                <div className="upload-actions">
                    <Button
                        onClick={handleUpload}
                        disabled={!file || uploading}
                        loading={uploading}
                        variant="primary"
                        fullWidth
                    >
                        {uploading ? 'Uploading...' : 'Upload File'}
                    </Button>

                    {file && !uploading && (
                        <Button
                            onClick={() => setFile(null)}
                            variant="ghost"
                            fullWidth
                        >
                            Clear Selection
                        </Button>
                    )}
                </div>
            </Card>

            {error && (
                <Card className="result-card error-card">
                    <div className="result-icon">
                        <XCircle size={32} />
                    </div>
                    <div>
                        <h3 className="result-title">Upload Failed</h3>
                        <p className="result-text">{error}</p>
                    </div>
                </Card>
            )}

            {result && (
                <Card className="result-card success-card">
                    <div className="result-icon success">
                        <CheckCircle size={32} />
                    </div>
                    <div className="result-content">
                        <h3 className="result-title">Upload Successful!</h3>
                        <p className="result-text">{result.message}</p>

                        {result.stats && (
                            <div className="stats-grid">
                                <div className="stat-item">
                                    <span className="stat-label">Total Clients</span>
                                    <span className="stat-value">{result.stats.total_clients}</span>
                                </div>
                                <div className="stat-item">
                                    <span className="stat-label">Total Groups</span>
                                    <span className="stat-value">{result.stats.total_groups}</span>
                                </div>
                                <div className="stat-item">
                                    <span className="stat-label">Total Loans</span>
                                    <span className="stat-value">{result.stats.total_loans}</span>
                                </div>
                                <div className="stat-item">
                                    <span className="stat-label">Portfolio</span>
                                    <span className="stat-value">
                                        {result.stats.total_loan_portfolio?.toLocaleString()} UGX
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                </Card>
            )}
        </div>
    );
};

export default FileUpload;
