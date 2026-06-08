import { useState, useRef } from 'react';
import { Upload, ShieldCheck, XCircle, FileImage, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { verifyDocument } from '../../services/api';
import './DocumentVerification.css';

const RESULT_CONFIG = {
    'NID': {
        icon: ShieldCheck,
        colorClass: 'result-nid',
        label: 'National Identity Card (NID)',
        description: 'This document has been identified as a valid National ID card.',
    },
    'Passport': {
        icon: ShieldCheck,
        colorClass: 'result-passport',
        label: 'Passport',
        description: 'This document has been identified as a valid Passport.',
    },
    'Does not match NID or Passport format': {
        icon: XCircle,
        colorClass: 'result-nomatch',
        label: 'No Match',
        description: 'This image does not match NID or Passport format.',
    },
};

const DocumentVerification = () => {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const inputRef = useRef(null);

    const handleFileChange = (e) => {
        const selected = e.target.files[0];
        setResult(null);
        setError(null);

        if (!selected) return;

        const ext = selected.name.split('.').pop().toLowerCase();
        if (!['jpg', 'jpeg'].includes(ext)) {
            setFile(null);
            setPreview(null);
            setError('Only JPG/JPEG images are accepted. Please upload a .jpg or .jpeg file.');
            return;
        }

        if (preview) URL.revokeObjectURL(preview);
        setFile(selected);
        setPreview(URL.createObjectURL(selected));
    };

    const handleDrop = (e) => {
        e.preventDefault();
        const dropped = e.dataTransfer.files[0];
        if (dropped) {
            const syntheticEvent = { target: { files: [dropped] } };
            handleFileChange(syntheticEvent);
        }
    };

    const handleDragOver = (e) => e.preventDefault();

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!file) {
            setError('Please select a JPEG image first.');
            return;
        }

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const res = await verifyDocument(file);
            if (res.success) {
                setResult(res.document_type);
            } else {
                setError(res.error || 'Verification failed. Please try again.');
            }
        } catch (err) {
            setError(
                typeof err === 'string'
                    ? err
                    : err?.error || 'Failed to connect to the server.'
            );
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        if (preview) URL.revokeObjectURL(preview);
        setFile(null);
        setPreview(null);
        setResult(null);
        setError(null);
        if (inputRef.current) inputRef.current.value = '';
    };

    const resultConfig = result ? RESULT_CONFIG[result] : null;

    return (
        <div className="doc-verify-page">
            <div className="doc-verify-header">
                <div className="doc-verify-icon">
                    <ShieldCheck size={32} />
                </div>
                <div>
                    <h1 className="doc-verify-title">Document Verification</h1>
                    <p className="doc-verify-subtitle">
                        Upload a JPG/JPEG image to verify if it is a National ID card or Passport
                    </p>
                </div>
            </div>

            <div className="doc-verify-content">
                <div className="doc-verify-card glass">
                    <form onSubmit={handleSubmit}>
                        <div
                            className={`doc-upload-zone ${file ? 'has-file' : ''}`}
                            onDrop={handleDrop}
                            onDragOver={handleDragOver}
                            onClick={() => !file && inputRef.current?.click()}
                        >
                            <input
                                ref={inputRef}
                                type="file"
                                accept=".jpg,.jpeg"
                                onChange={handleFileChange}
                                className="doc-file-input"
                                aria-label="Upload document image"
                            />

                            {preview ? (
                                <div className="doc-preview-wrapper">
                                    <img
                                        src={preview}
                                        alt="Document preview"
                                        className="doc-preview-image"
                                    />
                                    <div className="doc-file-info">
                                        <FileImage size={16} />
                                        <span className="doc-file-name">{file.name}</span>
                                        <span className="doc-file-size">
                                            ({(file.size / 1024).toFixed(1)} KB)
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <div className="doc-upload-placeholder">
                                    <div className="doc-upload-icon">
                                        <Upload size={40} />
                                    </div>
                                    <p className="doc-upload-text">
                                        Drag & drop or <span className="doc-upload-link">browse</span>
                                    </p>
                                    <p className="doc-upload-hint">JPG / JPEG only &bull; Max 10MB</p>
                                </div>
                            )}
                        </div>

                        {error && (
                            <div className="doc-alert doc-alert-error">
                                <AlertCircle size={18} />
                                <span>{error}</span>
                            </div>
                        )}

                        <div className="doc-actions">
                            <button
                                type="submit"
                                className="doc-btn-primary"
                                disabled={!file || loading}
                            >
                                {loading ? (
                                    <>
                                        <Loader2 size={18} className="spin" />
                                        Analyzing...
                                    </>
                                ) : (
                                    <>
                                        <ShieldCheck size={18} />
                                        Verify Document
                                    </>
                                )}
                            </button>

                            {file && (
                                <button
                                    type="button"
                                    className="doc-btn-secondary"
                                    onClick={handleReset}
                                    disabled={loading}
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                    </form>
                </div>

                {resultConfig && (
                    <div className={`doc-result-card glass ${resultConfig.colorClass}`}>
                        <div className="doc-result-icon">
                            <resultConfig.icon size={40} />
                        </div>
                        <div className="doc-result-body">
                            <div className="doc-result-badge">{resultConfig.label}</div>
                            <p className="doc-result-desc">{resultConfig.description}</p>
                        </div>
                        <CheckCircle size={24} className="doc-result-check" />
                    </div>
                )}

                <div className="doc-info-card glass">
                    <h3 className="doc-info-title">Supported Document Types</h3>
                    <div className="doc-info-grid">
                        <div className="doc-info-item">
                            <ShieldCheck size={20} className="doc-info-icon nid" />
                            <div>
                                <strong>National ID (NID)</strong>
                                <p>Any government-issued national identity card from any country</p>
                            </div>
                        </div>
                        <div className="doc-info-item">
                            <ShieldCheck size={20} className="doc-info-icon passport" />
                            <div>
                                <strong>Passport</strong>
                                <p>Any country&apos;s passport booklet or biographical data page</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DocumentVerification;
