import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Lock, Sparkles } from 'lucide-react';
import { useTheme } from '../../context';

export function AuthPlaceholder() {
  const navigate = useNavigate();
  const { theme } = useTheme();

  return (
    <div className="auth-placeholder-wrapper" data-theme={theme}>
      <div className="auth-placeholder-card">
        <div className="auth-placeholder-glow" />
        <div className="auth-icon-badge">
          <Lock size={28} className="auth-icon" />
        </div>
        <span className="auth-step-pill">
          <Sparkles size={14} />
          <span>Milestone 3 Ahead</span>
        </span>
        <h1 className="auth-placeholder-title">
          Authentication Suite
        </h1>
        <p className="auth-placeholder-desc">
          You navigated to the planned <code>/login</code> route. The purple atmospheric sign-in
          composition from your reference screenshot is planned for <strong>Milestone 3</strong>,
          including 1-click hackathon demo access, email authentication, and password recovery.
        </p>

        <div className="auth-placeholder-actions">
          <button
            type="button"
            className="auth-back-btn"
            onClick={() => navigate('/')}
          >
            <ArrowLeft size={16} />
            <span>Return to Landing Page</span>
          </button>
        </div>
      </div>
    </div>
  );
}
