import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, CheckCircle2, KeyRound, Mail } from 'lucide-react';
import { AuthLayout } from './AuthLayout';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !email.includes('@')) {
      setError('Please provide a valid work email address.');
      return;
    }

    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setSubmitted(false);setError('Email reset is not configured. Ask the administrator to rotate the private server password.');
    }, 600);
  };

  return (
    <AuthLayout>
      <div className="auth-card">
        {/* Avatar header */}
        <div className="auth-avatar-header">
          <div className="auth-avatar-circle">
            <KeyRound size={24} color="#7896B0" />
          </div>
          <h1 className="auth-title">Reset Password</h1>
          <p className="auth-subtitle">
            Email recovery is not configured. Ask the administrator to rotate the private server password.
          </p>
        </div>

        {submitted ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', textAlign: 'center' }}>
            <div className="auth-disclaimer-box" role="status">
              <CheckCircle2 size={16} color="#34d399" style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Email Reset Unavailable:</strong> No email was sent.
                Ask the administrator to rotate the private server password.
              </div>
            </div>

            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
              Recovery instructions dispatched for <strong>{email}</strong>.
            </p>

            <Link to="/login" className="auth-submit-btn" style={{ textDecoration: 'none' }}>
              <ArrowLeft size={16} />
              <span>Return to Sign In</span>
            </Link>
          </div>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            {error && (
              <div className="auth-field-error" role="alert">
                {error}
              </div>
            )}

            <div className="auth-field-group">
              <label className="auth-label" htmlFor="reset-email-input">
                Email Address
              </label>
              <div className="auth-input-wrapper">
                <Mail size={18} className="auth-input-icon" />
                <input disabled
                  id="reset-email-input"
                  type="email"
                  className="auth-input"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={true}
            >
              {loading ? (
                <span>Sending Instructions...</span>
              ) : (
                <>
                  <span>Email reset unavailable</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        )}

        {/* Footer Prompt */}
        <div className="auth-footer-prompt">
          <span>Remembered your password?</span>
          <Link to="/login" className="auth-switch-link">
            Back to login
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
