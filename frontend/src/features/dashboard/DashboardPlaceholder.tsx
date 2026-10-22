import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, LogOut, ShieldCheck } from 'lucide-react';
import { useAuth, useTheme } from '../../context';
import '../../styles/auth.css';

export function DashboardPlaceholder() {
  const { user, isAuthenticated, logout } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();

  // Route protection: redirect to login if session is not active
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="auth-viewport" data-theme={theme}>
      <div className="auth-ambient-glow" aria-hidden="true" />

      <main className="dashboard-placeholder-card">
        {/* Status header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="dot-indicator pulse" />
            <span style={{ fontSize: '12px', fontWeight: 700, color: '#34d399', letterSpacing: '0.05em' }}>
              AUTHENTICATED SESSION ACTIVE
            </span>
          </div>
          <button
            type="button"
            className="auth-nav-back"
            onClick={handleSignOut}
            style={{ cursor: 'pointer' }}
          >
            <LogOut size={14} />
            <span>Sign Out</span>
          </button>
        </div>

        {/* User Card */}
        <div className="user-profile-summary">
          <div className="user-profile-avatar">
            {user.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
          </div>
          <div className="user-profile-details">
            <span className="user-profile-name">{user.name}</span>
            <span className="user-profile-meta">{user.email} • {user.businessName}</span>
          </div>
        </div>

        {/* Readiness Note */}
        <div className="auth-disclaimer-box" style={{ background: 'rgba(56, 189, 248, 0.08)', borderColor: 'rgba(56, 189, 248, 0.25)', color: '#7896B0' }}>
          <ShieldCheck size={18} style={{ flexShrink: 0, marginTop: 2, color: 'var(--accent-blue)' }} />
          <div>
            <strong>Milestone 3 Authentication Complete:</strong> Your session was authenticated and validated through
            the auth state engine. The full financial intelligence dashboard with AdminCN layout, real-time widgets,
            and cash metrics is planned for <strong>Milestone 4</strong>.
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <Link
            to="/"
            className="auth-back-btn"
            style={{ flex: 1, textDecoration: 'none' }}
          >
            <ArrowLeft size={16} />
            <span>Return to Landing Page</span>
          </Link>

          <button
            type="button"
            className="demo-fast-btn"
            onClick={handleSignOut}
            style={{ padding: '12px 20px', borderRadius: 'var(--radius-full)' }}
          >
            <LogOut size={16} />
            <span>End Demo Session</span>
          </button>
        </div>

        <div style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
          Session ID: <code>{user.id}</code> • Standard: RFC-8785 Canonical Identity
        </div>
      </main>
    </div>
  );
}
