import React, { useState, useRef, useCallback } from 'react';

const API_BASE = '/api';
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * EmlUpload — polished drag-and-drop .eml file upload component.
 * Requires authentication. Shows extracted metadata before summarizing.
 */
export default function EmlUpload({
  token,
  onOpenAuthModal,
  onSummarizeUploadedEmail,
  isSummarizing,
}) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [extractedInfo, setExtractedInfo] = useState(null);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const processFile = useCallback(async (selectedFile) => {
    setError(null);
    setExtractedInfo(null);

    if (!token) {
      setError('Please sign in to upload .eml files.');
      onOpenAuthModal('login');
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith('.eml')) {
      setError('Unsupported format. Please upload a standard .eml email file.');
      return;
    }

    if (selectedFile.size > MAX_SIZE_BYTES) {
      setError('File exceeds the 10 MB size limit. Please trim the message history.');
      return;
    }

    if (selectedFile.size === 0) {
      setError('The selected file is empty (0 bytes). Please choose a valid .eml file.');
      return;
    }

    setFile(selectedFile);
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch(`${API_BASE}/upload-eml`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        setError(
          data.message ||
          data.error ||
          (res.status === 429
            ? 'Upload rate limit reached. Please wait before trying again.'
            : 'Failed to parse the .eml file. Please verify it is a valid email.')
        );
      } else {
        setExtractedInfo(data);
      }
    } catch (err) {
      setError(`Upload error: ${err.message}. Please check your connection.`);
    } finally {
      setIsUploading(false);
    }
  }, [token, onOpenAuthModal]);

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (f) processFile(f);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) processFile(f);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (token) fileInputRef.current?.click();
      else onOpenAuthModal('login');
    }
  };

  const handleReset = () => {
    setFile(null);
    setExtractedInfo(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

      {/* Auth notice */}
      {!token && (
        <div className="auth-notice" role="alert">
          <span>🔒 <strong>Sign in required</strong> — You must be signed in to upload .eml files.</span>
          <button
            className="btn-primary btn-sm"
            onClick={() => onOpenAuthModal('login')}
            aria-label="Sign in to upload files"
          >
            Sign In Now
          </button>
        </div>
      )}

      {/* Dropzone — shown when no file is extracted yet */}
      {!extractedInfo && (
        <>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".eml"
            style={{ display: 'none' }}
            disabled={!token || isUploading}
            aria-label="Choose .eml file"
            tabIndex="-1"
          />
          <div
            className={`dropzone ${isDragging ? 'dragover' : ''} ${!token ? 'dropzone-disabled' : ''}`}
            role="button"
            tabIndex={0}
            aria-label="Drag and drop an .eml file here or press Enter to browse"
            aria-disabled={!token}
            onDragOver={(e) => { e.preventDefault(); if (token) setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => { if (token) fileInputRef.current?.click(); else onOpenAuthModal('login'); }}
            onKeyDown={handleKeyDown}
          >
            <div className="dropzone-icon-wrap" aria-hidden="true">
              {isUploading ? '⏳' : '📁'}
            </div>
            <div className="dropzone-title">
              {isUploading ? 'Parsing .eml structure…' : 'Drop .eml File or Click to Browse'}
            </div>
            <p className="dropzone-hint">
              Supports RFC-822 MIME emails — headers, multipart text/plain, and HTML fallback.
              Attachments are safely skipped. Maximum size: 10 MB.
            </p>
            {!isUploading && (
              <button
                type="button"
                className="btn-secondary"
                disabled={!token}
                tabIndex="-1"
                aria-hidden="true"
              >
                Browse Computer (.eml)
              </button>
            )}
            {isUploading && (
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: '0.5rem' }}>
                <span className="spinner-dark" aria-hidden="true" />
              </div>
            )}
          </div>
        </>
      )}

      {/* Error */}
      {error && (
        <div className="error-banner" role="alert">
          <span className="error-banner-icon" aria-hidden="true">❌</span>
          <div>
            <div className="error-banner-title">Upload Failed</div>
            <div className="error-banner-msg">{error}</div>
          </div>
        </div>
      )}

      {/* Extracted email inspection card */}
      {extractedInfo && (
        <div className="eml-card">
          <div className="eml-card-header">
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <span className="eml-file-badge">📄 {extractedInfo.filename}</span>
              <h2 className="eml-subject" style={{ marginTop: '0.25rem' }}>{extractedInfo.subject}</h2>
            </div>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={handleReset}
              disabled={isSummarizing}
              aria-label="Upload a different file"
            >
              ↩ Change File
            </button>
          </div>

          <div className="eml-meta-grid">
            <div className="eml-meta-item">
              <span className="eml-meta-label">From:</span>
              <span className="eml-meta-val">{extractedInfo.from_sender}</span>
            </div>
            <div className="eml-meta-item">
              <span className="eml-meta-label">To:</span>
              <span className="eml-meta-val">{extractedInfo.to_recipients}</span>
            </div>
            <div className="eml-meta-item">
              <span className="eml-meta-label">Date:</span>
              <span className="eml-meta-val">{extractedInfo.date}</span>
            </div>
            <div className="eml-meta-item">
              <span className="eml-meta-label">Length:</span>
              <span className="eml-meta-val">{extractedInfo.char_count?.toLocaleString()} characters</span>
            </div>
            {extractedInfo.has_attachments && (
              <div className="eml-meta-item">
                <span className="eml-meta-label">Attachments:</span>
                <span className="eml-meta-val" style={{ color: 'var(--info)' }}>
                  📎 Detected — safely bypassed
                </span>
              </div>
            )}
          </div>

          <div className="eml-body-wrap">
            <label className="field-label" htmlFor="eml-body-preview">
              Extracted Message Body
            </label>
            <div
              id="eml-body-preview"
              className="body-preview-box"
              role="region"
              aria-label="Extracted email body preview"
              tabIndex={0}
            >
              {extractedInfo.body}
            </div>
          </div>

          <div className="eml-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => onSummarizeUploadedEmail(extractedInfo)}
              disabled={isSummarizing}
              aria-busy={isSummarizing}
            >
              {isSummarizing ? (
                <><span className="spinner" aria-hidden="true" /> Analyzing email thread…</>
              ) : (
                'Summarize Extracted Email ✨'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
