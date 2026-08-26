import { useState, useRef } from 'react';
import {
    ScanLine, Upload, FileImage, Loader2, AlertCircle,
    CheckCircle, XCircle, Copy, Check, Globe,
} from 'lucide-react';
import { scanIDCard } from '../../services/api';
import './NIDVoterIDScanner.css';

const ACCEPTED_FORMATS = ['jpg', 'jpeg', 'png', 'webp'];

const EXTRACTOR_LABELS = {
    vision: 'Cloud Vision',
    claude: 'Claude Vision',
    easyocr: 'EasyOCR (offline)',
    ollama: 'Ollama (local)',
};

const CONFIDENCE_CONFIG = {
    high:    { label: 'High Confidence',   cls: 'conf-high' },
    medium:  { label: 'Medium Confidence', cls: 'conf-medium' },
    low:     { label: 'Low Confidence',    cls: 'conf-low' },
    unknown: { label: 'Unknown',           cls: 'conf-low' },
};

const COUNTRY_INFO = [
    { flag: '🇺🇬', name: 'Uganda',     fmt: 'NIN (CM/CF + 13 chars)' },
    { flag: '🇰🇪', name: 'Kenya',      fmt: 'NID (7–8 digits)' },
    { flag: '🇹🇿', name: 'Tanzania',   fmt: 'NIDA (20 digits)' },
    { flag: '🇿🇲', name: 'Zambia',     fmt: 'NRC (xxx/xx/x)' },
    { flag: '🇧🇩', name: 'Bangladesh', fmt: 'NID (10 or 17 digits)' },
    { flag: '🌍',  name: 'Any country', fmt: 'Generic extraction' },
];

const NIDVoterIDScanner = () => {
    const [file, setFile]       = useState(null);
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult]   = useState(null);
    const [error, setError]     = useState(null);
    const [copied, setCopied]   = useState(false);
    const inputRef = useRef(null);

    const handleFileChange = (e) => {
        const selected = e.target.files[0];
        setResult(null);
        setError(null);
        if (!selected) return;

        const ext = selected.name.split('.').pop().toLowerCase();
        if (!ACCEPTED_FORMATS.includes(ext)) {
            setFile(null);
            setPreview(null);
            setError('Only JPG, PNG, or WebP images are accepted.');
            return;
        }

        if (preview) URL.revokeObjectURL(preview);
        setFile(selected);
        setPreview(URL.createObjectURL(selected));
    };

    const handleDrop = (e) => {
        e.preventDefault();
        const dropped = e.dataTransfer.files[0];
        if (dropped) handleFileChange({ target: { files: [dropped] } });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!file) { setError('Please select an image first.'); return; }
        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const res = await scanIDCard(file);
            if (res.success) {
                setResult(res.data);
            } else {
                setError(res.error || 'Scan failed. Please try again.');
            }
        } catch (err) {
            setError(typeof err === 'string' ? err : err?.error || 'Failed to connect to the server.');
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        if (preview) URL.revokeObjectURL(preview);
        setFile(null); setPreview(null); setResult(null);
        setError(null); setCopied(false);
        if (inputRef.current) inputRef.current.value = '';
    };

    const handleCopyID = () => {
        if (result?.id_number) {
            navigator.clipboard.writeText(result.id_number);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    const confCfg = result
        ? (CONFIDENCE_CONFIG[result.confidence] || CONFIDENCE_CONFIG.unknown)
        : null;

    return (
        <div className="nid-page">
            <div className="nid-header">
                <div className="nid-header-icon">
                    <ScanLine size={32} />
                </div>
                <div>
                    <h1 className="nid-title">ID Card Scanner</h1>
                    <p className="nid-subtitle">
                        Upload any national ID or Voter ID card — extracts name and ID number
                    </p>
                </div>
            </div>

            <div className="nid-content">
                
                <div className="nid-card glass">
                    <form onSubmit={handleSubmit}>
                        <div
                            className={`nid-upload-zone ${file ? 'has-file' : ''}`}
                            onDrop={handleDrop}
                            onDragOver={(e) => e.preventDefault()}
                            onClick={() => !file && inputRef.current?.click()}
                        >
                            <input
                                ref={inputRef}
                                type="file"
                                accept=".jpg,.jpeg,.png,.webp"
                                onChange={handleFileChange}
                                className="nid-file-input"
                                aria-label="Upload ID card image"
                            />
                            {preview ? (
                                <div className="nid-preview-wrapper">
                                    <img src={preview} alt="ID card preview" className="nid-preview-image" />
                                    <div className="nid-file-info">
                                        <FileImage size={16} />
                                        <span className="nid-file-name">{file.name}</span>
                                        <span className="nid-file-size">
                                            ({(file.size / 1024).toFixed(1)} KB)
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <div className="nid-upload-placeholder">
                                    <div className="nid-upload-icon"><Upload size={40} /></div>
                                    <p className="nid-upload-text">
                                        Drag & drop or <span className="nid-upload-link">browse</span>
                                    </p>
                                    <p className="nid-upload-hint">JPG · PNG · WebP &bull; Max 10 MB</p>
                                </div>
                            )}
                        </div>

                        {error && (
                            <div className="nid-alert nid-alert-error">
                                <AlertCircle size={18} />
                                <span>{error}</span>
                            </div>
                        )}

                        <div className="nid-actions">
                            <button
                                type="submit"
                                className="nid-btn-primary"
                                disabled={!file || loading}
                            >
                                {loading ? (
                                    <><Loader2 size={18} className="spin" /> Scanning...</>
                                ) : (
                                    <><ScanLine size={18} /> Scan ID Card</>
                                )}
                            </button>
                            {file && (
                                <button
                                    type="button"
                                    className="nid-btn-secondary"
                                    onClick={handleReset}
                                    disabled={loading}
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                    </form>
                </div>

                {result && (
                    <div className={`nid-result-card glass ${result.id_valid ? 'result-valid' : 'result-partial'}`}>
                        <div className="nid-result-top">
                            <div className={`nid-result-icon ${result.id_valid ? 'icon-valid' : 'icon-partial'}`}>
                                {result.id_valid ? <CheckCircle size={32} /> : <XCircle size={32} />}
                            </div>
                            <div className="nid-result-badges">
                                <span className={`nid-conf-badge ${confCfg.cls}`}>
                                    {confCfg.label}
                                </span>
                                <span className="nid-extractor-badge">
                                    via {EXTRACTOR_LABELS[result.extractor] || 'Vision model'}
                                </span>
                            </div>
                        </div>

                        <div className="nid-result-fields">
                            <div className="nid-field">
                                <span className="nid-field-label">Full Name</span>
                                <span className="nid-field-value nid-name">
                                    {result.name || '— not detected —'}
                                </span>
                            </div>

                            <div className="nid-field">
                                <span className="nid-field-label">ID Number</span>
                                <div className="nid-id-row">
                                    <span className="nid-field-value nid-id-number">
                                        {result.id_number || '— not detected —'}
                                    </span>
                                    {result.id_number && (
                                        <button
                                            className="nid-copy-btn"
                                            onClick={handleCopyID}
                                            title="Copy ID number"
                                            type="button"
                                        >
                                            {copied ? <Check size={14} /> : <Copy size={14} />}
                                        </button>
                                    )}
                                </div>
                                {result.id_number && (
                                    <span className={`nid-valid-badge ${result.id_valid ? 'badge-valid' : 'badge-unverified'}`}>
                                        {result.id_valid ? 'Format verified' : 'Format unverified'}
                                    </span>
                                )}
                            </div>

                            <div className="nid-field-row-inline">
                                <div className="nid-field">
                                    <span className="nid-field-label">
                                        <Globe size={12} style={{ display: 'inline', marginRight: '3px' }} />
                                        Country
                                    </span>
                                    <span className="nid-field-value">
                                        {result.country}
                                        {result.country_code !== 'XX' && (
                                            <span className="nid-country-code"> ({result.country_code})</span>
                                        )}
                                    </span>
                                </div>
                                <div className="nid-field">
                                    <span className="nid-field-label">Document Type</span>
                                    <span className="nid-field-value">{result.id_type}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                <div className="nid-info-card glass">
                    <h3 className="nid-info-title">Supported Countries &amp; Formats</h3>
                    <div className="nid-country-grid">
                        {COUNTRY_INFO.map(({ flag, name, fmt }) => (
                            <div className="nid-country-item" key={name}>
                                <span className="nid-flag">{flag}</span>
                                <div>
                                    <strong className="nid-country-name">{name}</strong>
                                    <p className="nid-country-fmt">{fmt}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default NIDVoterIDScanner;
