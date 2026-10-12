import React from 'react';

/**
 * Sidebar navigation component.
 * Renders the fixed dark sidebar with logo, nav items, Ollama status, and user controls.
 */
export default function Sidebar({
  activeTab,
  onTabChange,
  health,
  isCheckingHealth,
  onRefreshHealth,
  currentUser,
  onOpenAuthModal,
  onLogout,
  historyTotal,
  isMobileOpen,
  onMobileClose,
}) {
  const isConnected = health?.ollama_status === 'connected';
  const hasModel = Boolean(health?.model_available);

  const dotClass = !health
    ? 'dot-error'
    : !isConnected
    ? 'dot-error'
    : !hasModel
    ? 'dot-warn'
    : 'dot-ok';

  const statusText = !health
    ? 'Connecting…'
    : !isConnected
    ? 'AI offline'
    : !hasModel
    ? 'AI unavailable'
    : 'AI ready';

  const initials = currentUser
    ? (currentUser.full_name || currentUser.email)
        .split(/\s+/)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join('')
    : '';

  const navItems = [
    { id: 'dashboard', icon: '◈', label: 'Dashboard' },
    { id: 'summarize', icon: '✦', label: 'Summarize' },
    { id: 'history',   icon: '⊟', label: 'History', badge: currentUser ? historyTotal : null },
  ];

  return (
    <>
      {/* Overlay for mobile */}
      {isMobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`sidebar ${isMobileOpen ? 'sidebar-open' : ''}`}
        aria-label="Application sidebar"
      >
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-mark">
            <div className="logo-icon">✉</div>
            <div>
              <div className="logo-text">MailMind</div>
              <div className="logo-tagline">AI Email Intelligence</div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav" aria-label="Main navigation">
          <span className="nav-section-label">Menu</span>
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => {
                onTabChange(item.id);
                onMobileClose();
              }}
              aria-current={activeTab === item.id ? 'page' : undefined}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
              {item.badge != null && item.badge > 0 && (
                <span className="nav-badge" aria-label={`${item.badge} items`}>{item.badge}</span>
              )}
            </button>
          ))}
        </nav>

        {/* AI service status */}
        <div className="sidebar-status">
          <div className="ollama-status-row">
            <span className={`status-dot ${dotClass}`} aria-hidden="true" />
            <span>{statusText}</span>
            <button
              className="btn-refresh-mini"
              onClick={onRefreshHealth}
              disabled={isCheckingHealth}
              title="Check AI connectivity"
              aria-label="Refresh AI status"
            >
              {isCheckingHealth ? '⏳' : '↺'}
            </button>
          </div>
        </div>

        {/* User area */}
        <div className="sidebar-user">
          {currentUser ? (
            <div>
              <div className="user-info-row">
                <div className="user-avatar" aria-hidden="true">{initials}</div>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div className="user-name">
                    {currentUser.full_name || currentUser.email.split('@')[0]}
                  </div>
                  <div className="user-email-small" title={currentUser.email}>
                    {currentUser.email}
                  </div>
                </div>
                <button
                  className="btn-signout"
                  onClick={onLogout}
                  title="Sign out"
                  aria-label="Sign out"
                >
                  Out
                </button>
              </div>
            </div>
          ) : (
            <button
              className="btn-signin-sidebar"
              onClick={() => onOpenAuthModal('login')}
              aria-label="Sign in or register"
            >
              🔑 Sign In / Register
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
