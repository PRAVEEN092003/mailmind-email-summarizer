import React, { useMemo } from 'react';

/**
 * Safely parse or retrieve the structured summary object from a history record.
 * Handles both already-parsed objects and raw JSON strings.
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
 * Safely converts any value (string, number, or object) into a printable string.
 */
function safeString(val, fallback = '') {
  if (val == null) return fallback;
  if (typeof val === 'string') return val;
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (typeof val === 'object') {
    const candidate = val.item || val.task || val.text || val.point || val.title || val.name || val.description;
    if (typeof candidate === 'string') return candidate;
    if (typeof candidate === 'number') return String(candidate);
    return fallback;
  }
  return fallback;
}

/**
 * Dashboard — overview panel showing real stats derived from history data.
 * Never fabricates numbers — all values come from historyItems prop.
 */
export default function Dashboard({
  historyItems = [],
  historyTotal = 0,
  currentUser,
  onOpenAuthModal,
  onOpenSummary,
  onGoSummarize,
  onGoHistory,
}) {
  // Compute real stats from loaded history
  const stats = useMemo(() => {
    let high = 0;
    let pending = 0;
    for (const record of historyItems) {
      const sum = getSummaryObject(record);
      if (String(sum.urgency_level || '').toUpperCase() === 'HIGH') {
        high += 1;
      }
      const actions = Array.isArray(sum.action_items) ? sum.action_items : [];
      for (const a of actions) {
        const s = typeof a === 'object' && a?.status ? String(a.status).toLowerCase() : (typeof a === 'string' ? 'pending' : '');
        if (s === 'pending') pending += 1;
      }
    }
    return { total: historyTotal, high, pending };
  }, [historyItems, historyTotal]);

  // 6 most recent items for the quick-view grid
  const recent = useMemo(() => historyItems.slice(0, 6), [historyItems]);

  // All pending action items across recent history (up to 8)
  // CRITICAL FIX: Do NOT put `item` as a property because that would overwrite `a.item` with the entire record object!
  const pendingActions = useMemo(() => {
    const all = [];
    for (const record of historyItems) {
      const sum = getSummaryObject(record);
      const actions = Array.isArray(sum.action_items) ? sum.action_items : [];
      for (const a of actions) {
        const status = typeof a === 'object' && a?.status ? String(a.status).toLowerCase() : 'pending';
        if (status === 'pending' || status === 'uncertain') {
          const taskDescription = typeof a === 'string'
            ? a
            : safeString(a?.item || a?.task || a?.text, 'Pending task');

          const rawWho = typeof a === 'object' && a?.responsible_person
            ? (typeof a.responsible_person === 'object' ? safeString(a.responsible_person) : String(a.responsible_person).trim())
            : '';
          const who = (!rawWho || ['null', 'none', 'unassigned', 'n/a', 'undefined'].includes(rawWho.toLowerCase())) ? '' : rawWho;

          const rawDue = typeof a === 'object' && a?.deadline
            ? (typeof a.deadline === 'object' ? safeString(a.deadline) : String(a.deadline).trim())
            : '';
          const due = (!rawDue || ['null', 'none', 'not specified', 'no deadline stated', 'no deadline', 'n/a', 'undefined'].includes(rawDue.toLowerCase())) ? '' : rawDue;

          all.push({
            taskDescription,
            status,
            responsible_person: who,
            deadline: due,
            subject: record.subject || 'Untitled Thread',
            historyId: record.id,
            historyRecord: record, // SAFE: named historyRecord, NEVER 'item'
          });
        }
      }
      if (all.length >= 8) break;
    }
    return all;
  }, [historyItems]);

  const formatDate = (iso) => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = (now - d) / 1000;
      if (diff < 60) return 'just now';
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      if (diff < 172800) return 'yesterday';
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch { return ''; }
  };

  const urgencyClass = (level) => {
    const u = (level || '').toUpperCase();
    if (u === 'HIGH') return 'ubm-high';
    if (u === 'LOW') return 'ubm-low';
    return 'ubm-medium';
  };

  const taskClass = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'completed') return 'ars-completed';
    if (s === 'uncertain') return 'ars-uncertain';
    return 'ars-pending';
  };

  // Not logged in
  if (!currentUser) {
    return (
      <div className="workspace">
        <div className="page-header">
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Your AI-powered email intelligence overview</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
          {[
            { icon: '📧', label: 'Total Summaries', value: '—' },
            { icon: '🚨', label: 'High Priority', value: '—' },
            { icon: '📋', label: 'Pending Actions', value: '—' },
          ].map((s) => (
            <div key={s.label} className="stat-card">
              <div className="stat-icon">{s.icon}</div>
              <div className="stat-label">{s.label}</div>
              <div className="stat-value" style={{ color: 'var(--text-muted)' }}>{s.value}</div>
            </div>
          ))}
        </div>

        <div className="dash-empty">
          <div className="dash-empty-icon">🔒</div>
          <div className="dash-empty-title">Sign In to See Your Dashboard</div>
          <div className="dash-empty-desc" style={{ marginBottom: '1rem' }}>
            Your email summaries, action items, and high-priority threads will appear here after you sign in.
          </div>
          <button className="btn-primary" onClick={() => onOpenAuthModal('login')}>
            Sign In / Register
          </button>
        </div>
      </div>
    );
  }

  const firstName = currentUser.full_name
    ? currentUser.full_name.split(' ')[0]
    : currentUser.email.split('@')[0];

  return (
    <div className="workspace">
      <div className="page-header">
        <h1 className="page-title">Welcome back, {firstName} 👋</h1>
        <p className="page-subtitle">Here's your email intelligence overview</p>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📧</div>
          <div className="stat-label">Total Summaries</div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-sub">Email threads analysed</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🚨</div>
          <div className="stat-label">High Priority</div>
          <div className="stat-value" style={{ color: stats.high > 0 ? '#e11d48' : undefined }}>{stats.high}</div>
          <div className="stat-sub">Threads needing attention</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📋</div>
          <div className="stat-label">Pending Actions</div>
          <div className="stat-value" style={{ color: stats.pending > 0 ? '#d97706' : undefined }}>{stats.pending}</div>
          <div className="stat-sub">Across recent threads</div>
        </div>
      </div>

      {/* Recent Summaries */}
      <div className="dashboard-section">
        <div className="section-header">
          <span className="section-title">Recent Summaries</span>
          {historyTotal > 6 && (
            <button className="section-action" onClick={onGoHistory}>
              View all {historyTotal} →
            </button>
          )}
        </div>

        {recent.length === 0 ? (
          <div className="dash-empty">
            <div className="dash-empty-icon">📭</div>
            <div className="dash-empty-title">No summaries yet</div>
            <div className="dash-empty-desc" style={{ marginBottom: '0.875rem' }}>
              Summarize your first email thread to see it appear here.
            </div>
            <button className="btn-primary btn-sm" onClick={onGoSummarize}>
              Summarize a Thread ✨
            </button>
          </div>
        ) : (
          <div className="recent-grid">
            {recent.map((record) => {
              const sum = getSummaryObject(record);
              const urgency = String(sum?.urgency_level || 'MEDIUM').toUpperCase();
              const preview = record.raw_preview || sum?.overall_summary || '';
              return (
                <button
                  key={record.id}
                  className="recent-card"
                  onClick={() => onOpenSummary(record)}
                  aria-label={`Open summary: ${record.subject || 'Untitled Thread'}`}
                >
                  <div className="recent-subject">{record.subject || 'Untitled Thread'}</div>
                  {preview && (
                    <div className="recent-preview">{preview.slice(0, 140)}{preview.length > 140 ? '...' : ''}</div>
                  )}
                  <div className="recent-meta">
                    <span className="recent-date">{formatDate(record.created_at)}</span>
                    <span className={`urgency-badge-mini ${urgencyClass(urgency)}`}>{urgency}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Pending Action Items */}
      {pendingActions.length > 0 && (
        <div className="dashboard-section">
          <div className="section-header">
            <span className="section-title">Pending Action Items</span>
          </div>
          <div className="action-list-dash">
            {pendingActions.map((a, idx) => (
              <div
                key={idx}
                className="action-row-dash"
                style={{ cursor: a.historyRecord ? 'pointer' : 'default' }}
                onClick={() => {
                  if (a.historyRecord && onOpenSummary) {
                    onOpenSummary(a.historyRecord);
                  }
                }}
                title={a.historyRecord ? `Click to open summary #${a.historyId}` : undefined}
                role={a.historyRecord ? 'button' : undefined}
                tabIndex={a.historyRecord ? 0 : undefined}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && a.historyRecord && onOpenSummary) {
                    e.preventDefault();
                    onOpenSummary(a.historyRecord);
                  }
                }}
              >
                <span className={`action-row-status ${taskClass(a.status)}`}>
                  {(a.status || 'pending').charAt(0).toUpperCase() + (a.status || 'pending').slice(1)}
                </span>
                <span className="action-row-text">
                  {a.taskDescription}
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginLeft: '0.375rem' }}>
                    — {a.subject || 'Untitled'}
                  </span>
                </span>
                {(a.responsible_person || a.deadline) && (
                  <span className="action-row-who">
                    {a.responsible_person ? `👤 ${a.responsible_person}` : ''}
                    {a.deadline ? ` · ⏰ ${a.deadline}` : ''}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
