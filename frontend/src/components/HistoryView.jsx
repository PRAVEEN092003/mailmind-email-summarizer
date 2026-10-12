import React, { useState, useMemo } from 'react';

/**
 * Safely parse or retrieve the structured summary object from a history record.
 */
function getSummaryObject(record) {
  if (!record?.summary) return {};
  if (typeof record.summary === 'object' && record.summary !== null) {
    return record.summary;
  }
  if (typeof record.summary === 'string') {
    try {
      const parsed = JSON.parse(record.summary);
      return typeof parsed === 'object' && parsed !== null ? parsed : {};
    } catch {
      return { overall_summary: record.summary };
    }
  }
  return {};
}

/**
 * HistoryView — polished summary history with search, urgency badges,
 * inline delete confirmation, and proper auth gate.
 */
export default function HistoryView({
  historyItems,
  isLoading,
  error,
  onRefresh,
  onOpenSummary,
  onDeleteSummary,
  deletingId,
  currentUser,
  onOpenAuthModal,
}) {
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [search, setSearch] = useState('');

  const formatDate = (iso) => {
    if (!iso) return 'Just now';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch { return iso; }
  };

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return historyItems;
    return historyItems.filter((item) => {
      const sum = getSummaryObject(item);
      const subject = String(item.subject || '').toLowerCase();
      const preview = String(item.raw_preview || '').toLowerCase();
      const summaryText = String(sum.overall_summary || '').toLowerCase();
      return subject.includes(q) || preview.includes(q) || summaryText.includes(q);
    });
  }, [historyItems, search]);

  const urgencyClass = (level) => {
    const u = (level || '').toUpperCase();
    if (u === 'HIGH') return 'ubm-high';
    if (u === 'LOW') return 'ubm-low';
    return 'ubm-medium';
  };

  const handleConfirmDelete = (id) => {
    setConfirmDeleteId(null);
    onDeleteSummary(id);
  };

  // Not logged in
  if (!currentUser) {
    return (
      <div className="workspace">
        <div className="page-header">
          <h1 className="page-title">Summary History</h1>
          <p className="page-subtitle">Browse and manage your saved email summaries</p>
        </div>
        <div className="history-auth-gate">
          <div className="empty-icon" aria-hidden="true">🔒</div>
          <div className="empty-title">Sign In to View History</div>
          <p className="empty-desc">
            Your email summaries are private and tied to your account.
            Sign in to browse, re-open, and manage your saved threads.
          </p>
          <button
            className="btn-primary"
            onClick={() => onOpenAuthModal('login')}
            aria-label="Open sign in dialog"
          >
            🔑 Sign In / Register
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="workspace">
      <div className="page-header">
        <h1 className="page-title">Summary History</h1>
        <p className="page-subtitle">
          {historyItems.length} saved summaries for{' '}
          <strong>{currentUser.email}</strong>
        </p>
      </div>

      {/* Toolbar */}
      <div className="history-toolbar">
        <div className="search-box">
          <span className="search-icon" aria-hidden="true">🔍</span>
          <input
            id="history-search"
            type="search"
            className="search-input"
            placeholder="Search by subject or content…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search summaries"
          />
        </div>
        {search && (
          <span className="history-count-label">
            {filteredItems.length} of {historyItems.length} shown
          </span>
        )}
        <button
          className="btn-secondary btn-sm"
          onClick={onRefresh}
          disabled={isLoading}
          aria-label="Refresh history list"
          style={{ marginLeft: 'auto' }}
        >
          {isLoading ? <><span className="spinner-dark" style={{ width: 12, height: 12, borderWidth: 2 }} />Refreshing…</> : '↺ Refresh'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="error-banner" role="alert">
          <span className="error-banner-icon" aria-hidden="true">❌</span>
          <div>
            <div className="error-banner-title">Failed to load history</div>
            <div className="error-banner-msg">{error}</div>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && historyItems.length === 0 && (
        <div className="history-loading" aria-live="polite" aria-label="Loading summaries">
          <span className="spinner-dark" />
          <span>Loading your saved summaries…</span>
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && historyItems.length === 0 && (
        <div className="history-empty">
          <div className="empty-icon" aria-hidden="true">📭</div>
          <div className="empty-title">No Summaries Saved Yet</div>
          <p className="empty-desc">
            When you summarize an email thread it is automatically saved here under your account,
            so you can revisit it anytime.
          </p>
        </div>
      )}

      {/* No search results */}
      {!isLoading && !error && historyItems.length > 0 && filteredItems.length === 0 && (
        <div className="history-empty">
          <div className="empty-icon" aria-hidden="true">🔍</div>
          <div className="empty-title">No Results Found</div>
          <p className="empty-desc">No summaries match "{search}". Try a different search term.</p>
        </div>
      )}

      {/* History grid */}
      {filteredItems.length > 0 && (
        <div className="history-grid" role="list" aria-label="Saved summaries">
          {filteredItems.map((item) => {
            const sum = getSummaryObject(item);
            const urgency = String(sum.urgency_level || 'MEDIUM').toUpperCase();
            const preview = item.raw_preview || sum.overall_summary || '';
            const isDeleting = deletingId === item.id;

            return (
              <article key={item.id} className="history-card" role="listitem">
                {/* Header row */}
                <div className="hcard-top">
                  <h2 className="hcard-subject">{item.subject || 'Untitled Thread'}</h2>
                  <div className="hcard-badges">
                    <span
                      className={`urgency-badge-mini ${urgencyClass(urgency)}`}
                      aria-label={`Priority: ${urgency}`}
                    >
                      {urgency}
                    </span>
                    <span className="hcard-id" aria-label={`Record ID ${item.id}`}>
                      #{item.id}
                    </span>
                  </div>
                </div>

                {/* Preview */}
                {preview && (
                  <p className="hcard-preview" aria-label="Content preview">
                    {preview.slice(0, 200)}{preview.length > 200 ? '…' : ''}
                  </p>
                )}

                {/* Stats */}
                <div className="hcard-stats">
                  <span className="stat-pill">🤖 AI Summary</span>
                  <span className="stat-pill">📝 {item.char_count?.toLocaleString()} chars</span>
                  {item.processing_time_ms != null && (
                    <span className="stat-pill">⏱ {item.processing_time_ms}ms</span>
                  )}
                </div>

                <span className="hcard-date">📅 {formatDate(item.created_at)}</span>

                {/* Confirm delete / action buttons */}
                {confirmDeleteId === item.id ? (
                  <div className="delete-confirm-strip" role="alert">
                    <span className="delete-confirm-text">
                      ⚠️ Permanently delete <strong>#{item.id}</strong>?
                    </span>
                    <div className="delete-confirm-actions">
                      <button
                        className="btn-danger-solid btn-sm"
                        onClick={() => handleConfirmDelete(item.id)}
                        disabled={isDeleting}
                        aria-label={`Confirm delete summary ${item.id}`}
                      >
                        {isDeleting ? 'Deleting…' : 'Delete'}
                      </button>
                      <button
                        className="btn-secondary btn-sm"
                        onClick={() => setConfirmDeleteId(null)}
                        disabled={isDeleting}
                        aria-label="Cancel delete"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="hcard-actions">
                    <button
                      className="btn-open"
                      onClick={() => onOpenSummary(item)}
                      aria-label={`Open summary: ${item.subject || 'Untitled Thread'}`}
                    >
                      Open Summary ↗
                    </button>
                    <button
                      className="btn-danger btn-sm"
                      onClick={() => setConfirmDeleteId(item.id)}
                      disabled={isDeleting}
                      aria-label={`Delete summary ${item.id}`}
                      title="Delete this record"
                    >
                      🗑
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
