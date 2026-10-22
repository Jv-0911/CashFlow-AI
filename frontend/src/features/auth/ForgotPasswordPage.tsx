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
      setSubmitted(true);
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
            Enter your email to receive recovery instructions
          </p>
        </div>

        {submitted ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', textAlign: 'center' }}>
            <div className="auth-disclaimer-box" role="status">
              <CheckCircle2 size={16} color="#34d399" style={{ flexShrink: 0, marginTop: 2 }} />
              <div>
                <strong>Simulated Reset Link Sent:</strong> For security in demo mode, no real outbound emails are dispatched.
                You can now log in with your demo credentials or test the sign-in flow.
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
                <input
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
              disabled={loading}
            >
              {loading ? (
                <span>Sending Instructions...</span>
              ) : (
                <>
                  <span>Send Reset Instructions</span>
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
