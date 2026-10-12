import React, { useState } from 'react';

const API_BASE = '/api';

/**
 * AuthModal — premium sign-in / register dialog with full validation,
 * loading state, and accessible form fields.
 */
export default function AuthModal({ initialMode = 'login', onClose, onAuthSuccess }) {
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const switchMode = (m) => { setMode(m); setError(null); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) { setError('Email address is required.'); return; }
    if (!password)     { setError('Password is required.'); return; }

    if (mode === 'register') {
      if (password.length < 8) {
        setError('Password must be at least 8 characters long.');
        return;
      }
      if (!/[A-Z]/.test(password)) {
        setError('Password must contain at least one uppercase letter.');
        return;
      }
      if (!/[0-9]/.test(password)) {
        setError('Password must contain at least one digit.');
        return;
      }
    }

    setIsLoading(true);

    const endpoint = mode === 'login'
      ? `${API_BASE}/auth/login`
      : `${API_BASE}/auth/register`;

    const payload = mode === 'login'
      ? { email: email.trim(), password }
      : { email: email.trim(), password, full_name: fullName.trim() || undefined };

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (!res.ok || !data.access_token) {
        setError(
          data.message ||
          data.error ||
          (res.status === 429
            ? 'Too many attempts. Please wait a few minutes and try again.'
            : 'Authentication failed. Please check your credentials.')
        );
      } else {
        onAuthSuccess(data.access_token, data.user);
        onClose();
      }
    } catch (err) {
      setError(`Network error: ${err.message}. Is the backend running?`);
    } finally {
      setIsLoading(false);
    }
  };

  // Close on Escape key
  const handleKeyDown = (e) => { if (e.key === 'Escape') onClose(); };

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Title row */}
        <div className="modal-top">
          <h2 className="modal-title" id="auth-modal-title">
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </h2>
          <button
            className="btn-close"
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {/* Tab switch */}
        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button
            role="tab"
            aria-selected={mode === 'login'}
            className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => switchMode('login')}
          >
            Sign In
          </button>
          <button
            role="tab"
            aria-selected={mode === 'register'}
            className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => switchMode('register')}
          >
            Register
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Error */}
          {error && (
            <div className="auth-error" role="alert" aria-live="assertive">
              <span aria-hidden="true">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Full name (register only) */}
          {mode === 'register' && (
            <div className="form-group">
              <label className="field-label" htmlFor="auth-fullname">
                Full Name <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span>
              </label>
              <input
                id="auth-fullname"
                type="text"
                className="text-input"
                placeholder="e.g. Alex Smith"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={isLoading}
                autoComplete="name"
              />
            </div>
          )}

          {/* Email */}
          <div className="form-group">
            <label className="field-label" htmlFor="auth-email">
              Email Address <span className="required">*</span>
            </label>
            <input
              id="auth-email"
              type="email"
              className="text-input"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              required
              autoComplete={mode === 'login' ? 'username' : 'email'}
              aria-required="true"
            />
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="field-label" htmlFor="auth-password">
              Password <span className="required">*</span>
            </label>
            <input
              id="auth-password"
              type="password"
              className="text-input"
              placeholder={mode === 'register' ? 'Min 8 chars, 1 uppercase, 1 digit' : 'Enter your password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              aria-required="true"
              aria-describedby={mode === 'register' ? 'pw-hint' : undefined}
            />
            {mode === 'register' && (
              <p id="pw-hint" className="password-hint">
                Must be at least 8 characters and include an uppercase letter and a digit.
              </p>
            )}
          </div>

          <button
            type="submit"
            className="btn-primary btn-auth-submit"
            disabled={isLoading}
            aria-busy={isLoading}
          >
            {isLoading ? (
              <><span className="spinner" aria-hidden="true" /> Processing…</>
            ) : mode === 'login' ? (
              '🔑 Sign In'
            ) : (
              '✨ Create Account'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
