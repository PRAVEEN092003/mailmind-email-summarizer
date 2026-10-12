import React from 'react';

/**
 * Safely extracts a displayable string from any value (string, number, or object with text/name/item/etc).
 * Prevents "Objects are not valid as a React child" errors.
 */
function toDisplayString(val, fallback = '') {
  if (val == null) return fallback;
  if (typeof val === 'string') return val;
  if (typeof val === 'number' || typeof val === 'boolean') return String(val);
  if (typeof val === 'object') {
    const candidate =
      val.item ||
      val.text ||
      val.point ||
      val.decision ||
      val.task ||
      val.title ||
      val.name ||
      val.deadline ||
      val.question ||
      val.summary ||
      val.value ||
      val.description;
    if (typeof candidate === 'string') return candidate;
    if (typeof candidate === 'number') return String(candidate);
    return fallback;
  }
  return fallback;
}

/**
 * Safely converts an input into an array of items.
 */
function toArray(val) {
  if (Array.isArray(val)) return val;
  if (val == null) return [];
  if (typeof val === 'string' && val.trim()) return [val];
  if (typeof val === 'object' && Object.keys(val).length > 0) return [val];
  return [];
}

/**
 * Safely extracts and normalizes the structured summary object from responseData.
 * Handles:
 * - responseData.data (standard API response)
 * - responseData.summary (history record object)
 * - Raw JSON strings (without double parsing)
 * - Nested summary dictionaries
 */
function extractSummary(responseData) {
  if (!responseData) return null;

  let raw = responseData.data ?? responseData.summary ?? responseData;

  // If raw is a JSON string, safely parse it
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === 'object' && parsed !== null) {
        raw = parsed;
      } else {
        return { overall_summary: raw };
      }
    } catch {
      return { overall_summary: raw };
    }
  }

  if (!raw || typeof raw !== 'object') {
    return null;
  }

  // Handle case where raw has an inner summary property
  if (raw.summary && typeof raw.summary === 'object' && !raw.overall_summary) {
    return raw.summary;
  }
  if (typeof raw.summary === 'string' && !raw.overall_summary) {
    try {
      const parsedInner = JSON.parse(raw.summary);
      if (typeof parsedInner === 'object' && parsedInner !== null) {
        return parsedInner;
      }
    } catch {
      return { overall_summary: raw.summary };
    }
  }

  return raw;
}

/**
 * SummaryResult — premium structured display of AI-generated email summary.
 * Built with full defensive rendering against malformed, null, or unexpected data types.
 */
export default function SummaryResult({ responseData }) {
  if (!responseData) return null;

  const summary = extractSummary(responseData);

  // If no summary could be derived, show a clean, friendly empty state instead of crashing
  if (!summary) {
    return (
      <div className="summary-wrap" id="summary-result-section" role="alert">
        <div className="card card-padded" style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📭</div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            No Summary Details Available
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
            The selected record does not contain valid structured summary data.
          </p>
        </div>
      </div>
    );
  }

  // 1. Executive summary string
  const overallSummary = toDisplayString(summary.overall_summary, '');

  // 2. Discussion points array
  const pointsList = toArray(summary.main_discussion_points)
    .map((pt) => toDisplayString(pt))
    .filter(Boolean);

  // 3. Decisions list (prefer confirmed_decisions, fallback to important_decisions)
  const confirmedList = toArray(summary.confirmed_decisions)
    .map((d) => toDisplayString(d))
    .filter(Boolean);
  const importantList = toArray(summary.important_decisions)
    .map((d) => toDisplayString(d))
    .filter(Boolean);
  const decisionsList = confirmedList.length > 0 ? confirmedList : importantList;

function sanitizeNullStr(val) {
  if (val == null) return null;
  const str = String(val).trim();
  if (['null', 'none', 'unassigned', 'not specified', 'no deadline stated', 'no deadline', 'n/a', 'undefined', ''].includes(str.toLowerCase())) {
    return null;
  }
  return str;
}

  // 4. Action items normalized list
  const rawActionItems = toArray(summary.action_items);
  const actionItemsList = rawActionItems.map((ai, idx) => {
    if (typeof ai === 'string') {
      const cleanText = sanitizeNullStr(ai) || 'Action item';
      return {
        id: idx,
        text: cleanText,
        responsible_person: null,
        deadline: null,
        status: 'pending',
      };
    }
    if (typeof ai === 'object' && ai !== null) {
      const text = toDisplayString(ai.item || ai.task || ai.text || ai.description, 'Action item');
      const rawWho = toDisplayString(ai.responsible_person || ai.assignee || ai.owner, null);
      const rawDue = toDisplayString(ai.deadline || ai.due_date || ai.due, null);
      const who = sanitizeNullStr(rawWho);
      const due = sanitizeNullStr(rawDue);
      const status = typeof ai.status === 'string' ? ai.status.toLowerCase() : 'pending';
      return {
        id: idx,
        text,
        responsible_person: who,
        deadline: due,
        status,
      };
    }
    return {
      id: idx,
      text: toDisplayString(ai, 'Action item'),
      responsible_person: null,
      deadline: null,
      status: 'pending',
    };
  });

  // 5. Deadlines array
  const deadlinesList = toArray(summary.deadlines)
    .map((dl) => toDisplayString(dl))
    .map(sanitizeNullStr)
    .filter(Boolean);

  // 6. Responsible persons array
  const personsList = toArray(summary.responsible_persons)
    .map((p) => toDisplayString(p))
    .map(sanitizeNullStr)
    .filter(Boolean);

  // 7. Unanswered questions array
  const questionsList = toArray(summary.unanswered_questions)
    .map((q) => toDisplayString(q))
    .filter(Boolean);

  // 8. Urgency level & rationale
  const normUrgency = toDisplayString(summary.urgency_level, 'MEDIUM').toUpperCase();
  const urgencyExplanation = toDisplayString(
    summary.urgency_explanation,
    'Assessed from conversation context and schedule.'
  );

  const urgencyClass =
    normUrgency === 'HIGH' ? 'u-high' : normUrgency === 'LOW' ? 'u-low' : 'u-medium';

  const urgencyEmoji =
    normUrgency === 'HIGH' ? '🚨' : normUrgency === 'LOW' ? '🟢' : '⚡';

  const fmtTime = (ms) => {
    if (ms == null || ms === 0) return null;
    if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.round(ms)}ms`;
  };

  const taskBadgeClass = (status) => {
    const s = (status || 'pending').toLowerCase();
    if (s === 'completed') return 'task-completed';
    if (s === 'uncertain') return 'task-uncertain';
    return 'task-pending';
  };

  const taskLabel = (status) => {
    const s = (status || 'pending').toLowerCase();
    if (s === 'completed') return '✓ Completed';
    if (s === 'uncertain') return '? Uncertain';
    return '⏳ Pending';
  };

  const subjectTitle = responseData.subject || responseData.raw_item?.subject;

  return (
    <div className="summary-wrap" id="summary-result-section" aria-label="Summary results">

      {/* Meta chips */}
      <div className="meta-bar" role="status" aria-label="Summary metadata">
        {responseData.is_cached ? (
          <span className="meta-chip chip-cached" title="Retrieved instantly from cache">
            <span>⚡</span> Cached
          </span>
        ) : (
          <span className="meta-chip chip-fresh" title="Generated live by AI">
            <span>✨</span> Live
          </span>
        )}
        <span className="meta-chip">
          <span>🤖</span> AI Summary
        </span>
        {fmtTime(responseData.processing_time_ms) && (
          <span className="meta-chip">
            <span>⏱</span> {fmtTime(responseData.processing_time_ms)}
          </span>
        )}
        {responseData.chars_processed > 0 && (
          <span className="meta-chip">
            <span>📝</span> {responseData.chars_processed.toLocaleString()} chars
          </span>
        )}
        {responseData.history_id && (
          <span className="meta-chip">
            <span>💾</span> #{responseData.history_id}
          </span>
        )}
        {subjectTitle && (
          <span className="meta-chip" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            <span>📧</span> {subjectTitle}
          </span>
        )}
      </div>

      {/* Urgency banner */}
      <div className={`urgency-strip ${urgencyClass}`} role="status" aria-label={`Urgency: ${normUrgency}`}>
        <span className="urgency-label" aria-hidden="true">
          {urgencyEmoji} {normUrgency} PRIORITY
        </span>
        <p className="urgency-rationale">
          <strong>Rationale:</strong>{' '}
          {urgencyExplanation}
        </p>
      </div>

      {/* 1. Executive Summary */}
      <section className="result-section section-accent-left" aria-labelledby="exec-summary-heading">
        <div className="result-header">
          <span className="result-icon" aria-hidden="true">📌</span>
          <h2 className="result-title" id="exec-summary-heading">Executive Summary</h2>
        </div>
        <p className="executive-text">{overallSummary || 'No summary available.'}</p>
      </section>

      {/* 2 & 3. Grid: Discussion Points + Decisions */}
      <div className="result-grid-2">
        {/* Discussion Points */}
        <section className="result-section" aria-labelledby="discussion-heading">
          <div className="result-header">
            <span className="result-icon" aria-hidden="true">💬</span>
            <h3 className="result-title" id="discussion-heading">Discussion Points</h3>
            <span className="count-chip" aria-label={`${pointsList.length} items`}>
              {pointsList.length}
            </span>
          </div>
          {pointsList.length === 0 ? (
            <p className="empty-hint">No primary discussion points identified.</p>
          ) : (
            <ul className="points-list" aria-label="Main discussion points">
              {pointsList.map((pt, i) => (
                <li key={i} className="point-item">
                  <span className="point-bullet" aria-hidden="true">•</span>
                  <span>{pt}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Confirmed Decisions */}
        <section className="result-section" aria-labelledby="decisions-heading">
          <div className="result-header">
            <span className="result-icon" aria-hidden="true">✅</span>
            <h3 className="result-title" id="decisions-heading">Confirmed Decisions</h3>
            <span className="count-chip">{decisionsList.length}</span>
          </div>
          {decisionsList.length === 0 ? (
            <p className="empty-hint">No definitive decisions confirmed in this thread.</p>
          ) : (
            <ul className="points-list" aria-label="Confirmed decisions">
              {decisionsList.map((dec, i) => (
                <li key={i} className="decision-item">
                  <span className="decision-check" aria-hidden="true">✔</span>
                  <span>{dec}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* 4. Action Items */}
      <section className="result-section" aria-labelledby="actions-heading">
        <div className="result-header">
          <span className="result-icon" aria-hidden="true">📋</span>
          <h3 className="result-title" id="actions-heading">Action Items & Tasks</h3>
          <span className="count-chip">{actionItemsList.length}</span>
        </div>
        {actionItemsList.length === 0 ? (
          <p className="empty-hint">No explicit action items assigned in this thread.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}
               role="list" aria-label="Action items">
            {actionItemsList.map((item, i) => (
              <div key={i} className="action-item-card" role="listitem">
                <div className="action-top">
                  <span className="action-index" aria-hidden="true">#{i + 1}</span>
                  <span className="action-text">{item.text}</span>
                  <span className={`task-badge ${taskBadgeClass(item.status)}`}
                        aria-label={`Status: ${item.status || 'pending'}`}>
                    {taskLabel(item.status)}
                  </span>
                </div>
                <div className="action-pills">
                  <span className={`pill ${item.responsible_person ? 'pill-owner' : 'pill-none'}`}>
                    👤 {item.responsible_person || 'Unassigned'}
                  </span>
                  <span className={`pill ${item.deadline ? 'pill-deadline' : 'pill-none'}`}>
                    ⏰ {item.deadline ? `Due: ${item.deadline}` : 'Not specified'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 5 & 6. Deadlines + Responsible Persons */}
      <div className="result-grid-2">
        <section className="result-section" aria-labelledby="deadlines-heading">
          <div className="result-header">
            <span className="result-icon" aria-hidden="true">📅</span>
            <h3 className="result-title" id="deadlines-heading">Deadlines Mentioned</h3>
            <span className="count-chip">{deadlinesList.length}</span>
          </div>
          {deadlinesList.length === 0 ? (
            <p className="empty-hint">No explicit deadlines mentioned.</p>
          ) : (
            <div className="tag-list" aria-label="Deadlines">
              {deadlinesList.map((dl, i) => (
                <span key={i} className="deadline-tag">⏰ {dl}</span>
              ))}
            </div>
          )}
        </section>

        <section className="result-section" aria-labelledby="persons-heading">
          <div className="result-header">
            <span className="result-icon" aria-hidden="true">👥</span>
            <h3 className="result-title" id="persons-heading">Responsible Persons</h3>
            <span className="count-chip">{personsList.length}</span>
          </div>
          {personsList.length === 0 ? (
            <p className="empty-hint">No specific assignees identified.</p>
          ) : (
            <div className="tag-list" aria-label="Responsible persons">
              {personsList.map((p, i) => (
                <span key={i} className="person-tag">👤 {p}</span>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* 7. Unanswered Questions */}
      <section
        className="result-section section-accent-amber"
        aria-labelledby="questions-heading"
      >
        <div className="result-header">
          <span className="result-icon" aria-hidden="true">❓</span>
          <h3 className="result-title" id="questions-heading">Unanswered Questions & Blockers</h3>
          <span className="count-chip">{questionsList.length}</span>
        </div>
        {questionsList.length === 0 ? (
          <p className="empty-hint">All raised questions appear resolved, or none were asked.</p>
        ) : (
          <ul className="points-list" aria-label="Unanswered questions">
            {questionsList.map((q, i) => (
              <li key={i} className="question-item">
                <span className="q-mark" aria-hidden="true">?</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
