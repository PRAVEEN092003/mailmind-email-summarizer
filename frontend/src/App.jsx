import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Header';
import OllamaAlert from './components/OllamaAlert';
import SummaryResult from './components/SummaryResult';
import HistoryView from './components/HistoryView';
import AuthModal from './components/AuthModal';
import EmlUpload from './components/EmlUpload';
import Dashboard from './components/Dashboard';
import { SAMPLE_THREADS } from './sampleThreads';

const API_BASE = '/api';

export default function App() {
  // ── Navigation state ───────────────────────────────────────
  const [activeTab, setActiveTab] = useState('dashboard'); // 'dashboard' | 'summarize' | 'history'
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  // ── Summarize workspace ───────────────────────────────────
  const [inputMode, setInputMode] = useState('paste'); // 'paste' | 'upload'
  const [emailContent, setEmailContent] = useState('');
  const [subject, setSubject] = useState('');
  const [maxChars] = useState(35000);
  const [isLoading, setIsLoading] = useState(false);
  const [summaryResult, setSummaryResult] = useState(null);
  const [error, setError] = useState(null);

  // ── Notification toast ────────────────────────────────────
  const [notification, setNotification] = useState(null);

  // ── Ollama health ────────────────────────────────────────
  const [health, setHealth] = useState(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  // ── Auth state ────────────────────────────────────────────
  const [token, setToken] = useState(() => localStorage.getItem('token') || null);
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('user');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login');

  // ── History state ─────────────────────────────────────────
  const [historyItems, setHistoryItems] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  // ── Helpers ───────────────────────────────────────────────
  const showNotification = useCallback((msg, type = 'info') => {
    setNotification({ msg, type });
    const timer = setTimeout(() => setNotification(null), 4500);
    return () => clearTimeout(timer);
  }, []);

  // ── Health check ──────────────────────────────────────────
  const checkHealth = useCallback(async () => {
    setIsCheckingHealth(true);
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        setHealth(await res.json());
      } else {
        setHealth({ ollama_status: 'unreachable', model_available: false });
      }
    } catch {
      setHealth({ ollama_status: 'unreachable', model_available: false });
    } finally {
      setIsCheckingHealth(false);
    }
  }, []);

  // ── History fetch ─────────────────────────────────────────
  const fetchHistory = useCallback(async (activeToken = token) => {
    if (!activeToken) {
      setHistoryItems([]);
      setHistoryTotal(0);
      return;
    }
    setIsHistoryLoading(true);
    setHistoryError(null);
    try {
      const res = await fetch(`${API_BASE}/history?limit=50&offset=0`, {
        headers: { Authorization: `Bearer ${activeToken}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setHistoryItems(data.items || []);
        setHistoryTotal(data.total || 0);
      } else if (res.status === 401) {
        handleLogout();
        setHistoryError('Session expired. Please sign in again.');
      } else {
        setHistoryError(data.message || 'Failed to retrieve history.');
      }
    } catch (err) {
      setHistoryError(`Network error: ${err.message}`);
    } finally {
      setIsHistoryLoading(false);
    }
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { checkHealth(); }, [checkHealth]);
  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  // ── Auth handlers ─────────────────────────────────────────
  const handleOpenAuthModal = (mode = 'login') => {
    setAuthModalMode(mode);
    setAuthModalOpen(true);
  };

  const handleAuthSuccess = (newToken, newUser) => {
    setToken(newToken);
    setCurrentUser(newUser);
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(newUser));
    showNotification(`Welcome, ${newUser.full_name || newUser.email}! 👋`, 'success');
    fetchHistory(newToken);
  };

  const handleLogout = () => {
    setToken(null);
    setCurrentUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setHistoryItems([]);
    setHistoryTotal(0);
    showNotification('Signed out successfully.', 'info');
  };

  // ── Summarize workspace handlers ──────────────────────────
  const handleLoadSample = (sample) => {
    setInputMode('paste');
    setEmailContent(sample.content);
    setSubject(sample.title);
    setError(null);
    setSummaryResult(null);
  };

  const handleClear = () => {
    setEmailContent('');
    setSubject('');
    setError(null);
    setSummaryResult(null);
  };

  const executeSummarize = async (content, subjectText) => {
    setIsLoading(true);
    setError(null);
    setSummaryResult(null);

    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      const res = await fetch(`${API_BASE}/summarize`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          email_content: content,
          subject: subjectText?.trim() || undefined,
        }),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        const msg =
          res.status === 429
            ? 'Rate limit reached. Please wait a minute before summarizing again.'
            : data.message || data.error || 'Failed to generate summary. Please try again.';
        setError(msg);
      } else {
        setSummaryResult(data);
        if (token) fetchHistory();
        showNotification(
          data.is_cached
            ? '⚡ Retrieved from cache!'
            : '✨ Thread summarized and saved to history.',
          'success',
        );
        setTimeout(() => {
          document.getElementById('summary-result-section')?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      }
    } catch (err) {
      setError(`Network error: Could not reach the server (${err.message}). Please ensure the service is running.`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSummarizePasted = (e) => {
    e.preventDefault();
    if (!emailContent.trim()) {
      setError('Please paste an email thread to summarize.');
      return;
    }
    executeSummarize(emailContent, subject);
  };

  const handleSummarizeUploadedEmail = (info) => {
    setEmailContent(info.body);
    setSubject(info.subject);
    executeSummarize(info.body, info.subject);
  };

// ── Error Boundary ─────────────────────────────────────────
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="workspace" style={{ padding: '2rem 1rem', textAlign: 'center' }}>
          <div className="card card-padded" style={{ maxWidth: 540, margin: '2rem auto' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚠️</div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
              Something went wrong displaying this view
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              className="btn-primary"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                if (this.props.onReset) this.props.onReset();
              }}
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

  // ── History handlers ──────────────────────────────────────
  const handleOpenSummary = (item) => {
    if (!item) return;

    let summaryObj = item.summary;
    if (typeof summaryObj === 'string') {
      try {
        summaryObj = JSON.parse(summaryObj);
      } catch (err) {
        console.warn('Failed to parse summary_json:', err);
        summaryObj = { overall_summary: item.summary };
      }
    }

    setSummaryResult({
      success: true,
      data: summaryObj || {},
      model_used: item.model_used,
      chars_processed: item.char_count,
      processing_time_ms: item.processing_time_ms,
      is_cached: true,
      history_id: item.id,
      content_hash: item.content_hash,
      schema_version: item.schema_version,
      subject: item.subject,
      raw_item: item,
    });
    if (item.original_content) {
      setEmailContent(item.original_content);
    } else if (item.raw_preview) {
      setEmailContent(item.raw_preview);
    }
    setSubject(item.subject || '');
    setError(null);
    setActiveTab('summarize');
    setInputMode('paste');
    setTimeout(() => {
      document.getElementById('summary-result-section')?.scrollIntoView({ behavior: 'smooth' });
    }, 150);
  };

  const handleDeleteSummary = async (id) => {
    if (!token) return;
    setDeletingId(id);
    try {
      const res = await fetch(`${API_BASE}/history/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showNotification(`Summary #${id} deleted.`, 'info');
        if (summaryResult?.history_id === id) {
          setSummaryResult((prev) => (prev ? { ...prev, history_id: null } : null));
        }
        await fetchHistory();
      } else {
        showNotification(data.message || `Failed to delete summary #${id}`, 'error');
      }
    } catch (err) {
      showNotification(`Delete failed: ${err.message}`, 'error');
    } finally {
      setDeletingId(null);
    }
  };

  const charCount = emailContent.length;
  const isOverLimit = charCount > maxChars;

  // ── Summarize workspace render ────────────────────────────
  const renderSummarize = () => (
    <div className="workspace">
      <div className="page-header">
        <h1 className="page-title">Summarize Email Thread</h1>
        <p className="page-subtitle">
          Paste a thread or upload a .eml file to extract structured insights.
        </p>
      </div>

      <OllamaAlert health={health} />

      {/* Input card */}
      <div className="card card-padded" style={{ marginBottom: '1.25rem' }}>
        {/* Mode strip + samples */}
        <div className="workspace-top">
          <div className="mode-strip" role="group" aria-label="Input mode">
            <button
              type="button"
              className={`mode-btn ${inputMode === 'paste' ? 'active' : ''}`}
              onClick={() => setInputMode('paste')}
              aria-pressed={inputMode === 'paste'}
            >
              📝 Paste Text
            </button>
            <button
              type="button"
              className={`mode-btn ${inputMode === 'upload' ? 'active' : ''}`}
              onClick={() => setInputMode('upload')}
              aria-pressed={inputMode === 'upload'}
            >
              📁 Upload .eml
            </button>
          </div>

          {inputMode === 'paste' && (
            <div className="sample-row">
              <span className="sample-label">Try sample:</span>
              {SAMPLE_THREADS.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  className="sample-chip"
                  onClick={() => handleLoadSample(s)}
                  title={s.title}
                >
                  {s.title}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Paste form */}
        {inputMode === 'paste' ? (
          <form onSubmit={handleSummarizePasted} aria-label="Email summarization form">
            <div className="form-group">
              <label className="field-label" htmlFor="thread-subject">
                Thread Subject / Title
                <span style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: '0.25rem' }}>
                  (optional)
                </span>
              </label>
              <input
                id="thread-subject"
                type="text"
                className="text-input"
                placeholder="e.g. Project Alpha Launch Date & Blocker Review"
                value={subject}
                onChange={(e) => {
                  setSubject(e.target.value);
                  if (summaryResult) setSummaryResult(null);
                }}
                disabled={isLoading}
                autoComplete="off"
              />
            </div>

            <div className="form-group">
              <div className="char-counter-row">
                <label className="field-label" htmlFor="thread-body">
                  Email Conversation Thread <span className="required">*</span>
                </label>
                <span
                  className={`char-counter ${isOverLimit ? 'over' : ''}`}
                  aria-live="polite"
                  aria-label={`Character count: ${charCount} of ${maxChars}`}
                >
                  {charCount.toLocaleString()} / {maxChars.toLocaleString()}
                </span>
              </div>
              <textarea
                id="thread-body"
                className={`textarea-input ${isOverLimit ? 'input-error-state' : ''}`}
                rows={12}
                placeholder="Paste the full email conversation thread here (including senders, timestamps, and replies)…"
                value={emailContent}
                onChange={(e) => {
                  setEmailContent(e.target.value);
                  if (summaryResult) setSummaryResult(null);
                }}
                disabled={isLoading}
                aria-required="true"
                aria-invalid={isOverLimit}
                aria-describedby={isOverLimit ? 'char-over-msg' : undefined}
              />
              {isOverLimit && (
                <p id="char-over-msg" style={{ color: 'var(--error)', fontSize: '0.78rem', marginTop: '0.25rem' }}>
                  Content exceeds {maxChars.toLocaleString()} character limit. Please trim the thread.
                </p>
              )}
            </div>

            <div className="actions-row">
              <button
                type="button"
                className="btn-secondary"
                onClick={handleClear}
                disabled={isLoading || (!emailContent && !subject)}
              >
                Clear
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={isLoading || !emailContent.trim() || isOverLimit}
                aria-busy={isLoading}
              >
                {isLoading ? (
                  <><span className="spinner" aria-hidden="true" /> Analyzing email thread…</>
                ) : (
                  'Summarize Thread ✨'
                )}
              </button>
            </div>
          </form>
        ) : (
          <EmlUpload
            token={token}
            onOpenAuthModal={handleOpenAuthModal}
            onSummarizeUploadedEmail={handleSummarizeUploadedEmail}
            isSummarizing={isLoading}
          />
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="error-banner" role="alert" aria-live="assertive">
          <span className="error-banner-icon" aria-hidden="true">❌</span>
          <div>
            <div className="error-banner-title">Summarization Failed</div>
            <div className="error-banner-msg">{error}</div>
          </div>
        </div>
      )}

      {/* Summary result */}
      {summaryResult && emailContent.trim() && <SummaryResult responseData={summaryResult} />}
    </div>
  );

  return (
    <div className="app-shell">
      {/* Mobile topbar */}
      <div className="mobile-topbar" aria-label="Mobile navigation bar">
        <button
          className="btn-hamburger"
          onClick={() => setIsMobileNavOpen((v) => !v)}
          aria-label={isMobileNavOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={isMobileNavOpen}
          aria-controls="sidebar"
        >
          {isMobileNavOpen ? '✕' : '☰'}
        </button>
        <span className="mobile-logo-text">MailMind</span>
        <span style={{ width: 36 }} />
      </div>

      {/* Sidebar */}
      <Sidebar
        id="sidebar"
        activeTab={activeTab}
        onTabChange={setActiveTab}
        health={health}
        isCheckingHealth={isCheckingHealth}
        onRefreshHealth={checkHealth}
        currentUser={currentUser}
        onOpenAuthModal={handleOpenAuthModal}
        onLogout={handleLogout}
        historyTotal={historyTotal}
        isMobileOpen={isMobileNavOpen}
        onMobileClose={() => setIsMobileNavOpen(false)}
      />

      {/* Main area */}
      <div className="main-area">
        {/* Mobile tab nav (shown below mobile topbar) */}
        <nav className="topnav" aria-label="Page navigation">
          {[
            { id: 'dashboard', icon: '◈', label: 'Dashboard' },
            { id: 'summarize', icon: '✦', label: 'Summarize' },
            { id: 'history', icon: '⊟', label: 'History', count: currentUser ? historyTotal : null },
          ].map((t) => (
            <button
              key={t.id}
              className={`topnav-btn ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => setActiveTab(t.id)}
              aria-current={activeTab === t.id ? 'page' : undefined}
            >
              {t.icon} {t.label}
              {t.count != null && t.count > 0 && (
                <span className="topnav-count">{t.count}</span>
              )}
            </button>
          ))}
        </nav>

        {/* Page content */}
        <main className="page-content" id="main-content" aria-label="Page content">
          <ErrorBoundary onReset={() => setActiveTab('dashboard')}>
            {activeTab === 'dashboard' && (
              <Dashboard
                historyItems={historyItems}
                historyTotal={historyTotal}
                currentUser={currentUser}
                onOpenAuthModal={handleOpenAuthModal}
                onOpenSummary={handleOpenSummary}
                onGoSummarize={() => {
                  setSummaryResult(null);
                  setEmailContent('');
                  setSubject('');
                  setActiveTab('summarize');
                }}
                onGoHistory={() => setActiveTab('history')}
              />
            )}

            {activeTab === 'summarize' && renderSummarize()}

            {activeTab === 'history' && (
              <HistoryView
                historyItems={historyItems}
                isLoading={isHistoryLoading}
                error={historyError}
                onRefresh={() => fetchHistory()}
                onOpenSummary={handleOpenSummary}
                onDeleteSummary={handleDeleteSummary}
                deletingId={deletingId}
                currentUser={currentUser}
                onOpenAuthModal={handleOpenAuthModal}
              />
            )}
          </ErrorBoundary>
        </main>

        {/* Footer */}
        <footer className="app-footer" role="contentinfo">
          <span className="footer-text">
            MailMind — AI Email Intelligence
          </span>
        </footer>
      </div>

      {/* Auth modal */}
      {authModalOpen && (
        <AuthModal
          initialMode={authModalMode}
          onClose={() => setAuthModalOpen(false)}
          onAuthSuccess={handleAuthSuccess}
        />
      )}

      {/* Toast */}
      {notification && (
        <div className="toast-wrap" aria-live="polite" aria-atomic="true">
          <div className={`toast toast-${notification.type}`} role="status">
            {notification.msg}
          </div>
        </div>
      )}
    </div>
  );
}
