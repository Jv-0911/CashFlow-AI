import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, Lock, Mail, Sparkles } from 'lucide-react';
import { useAuth } from '../../context';
import { AuthLayout } from './AuthLayout';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, demoLogin } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);
    // Simulate authentication processing
    setTimeout(() => {
      login(email, email.split('@')[0]);
      setLoading(false);
      navigate('/dashboard');
    }, 600);
  };

  const handleQuickDemo = () => {
    demoLogin();
    navigate('/dashboard');
  };

  const handleGoogleDemo = () => {
    demoLogin();
    navigate('/dashboard');
  };

  return (
    <AuthLayout>
      <div className="auth-card">
        {/* Avatar header matching screenshot */}
        <div className="auth-avatar-header">
          <div className="auth-avatar-circle">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="#7896B0" />
            </svg>
          </div>
          <h1 className="auth-title">Welcome Back</h1>
          <p className="auth-subtitle">Sign in to your CashFlow AI account</p>
        </div>

        {/* 1-Click Fast Hackathon Demo Access */}
        <div className="auth-demo-banner">
          <div className="demo-banner-info">
            <span className="demo-banner-title">
              <Sparkles size={14} color="#7896B0" />
              <span>Hackathon Demo Access</span>
            </span>
            <span className="demo-banner-sub">Pre-authenticated as Alex Morgan (NovaCraft)</span>
          </div>
          <button
            type="button"
            className="demo-fast-btn"
            onClick={handleQuickDemo}
          >
            <span>Instant Demo</span>
            <ArrowRight size={13} />
          </button>
        </div>

        {/* Form */}
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="auth-field-error" role="alert">
              {error}
            </div>
          )}

          <div className="auth-field-group">
            <label className="auth-label" htmlFor="email-input">
              Email Address
            </label>
            <div className="auth-input-wrapper">
              <Mail size={18} className="auth-input-icon" />
              <input
                id="email-input"
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

          <div className="auth-field-group">
            <label className="auth-label" htmlFor="password-input">
              <span>Password</span>
            </label>
            <div className="auth-input-wrapper">
              <Lock size={18} className="auth-input-icon" />
              <input
                id="password-input"
                type={showPassword ? 'text' : 'password'}
                className="auth-input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="auth-password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="auth-row-options">
            <label className="auth-remember-label">
              <input
                type="checkbox"
                className="auth-checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              <span>Remember me</span>
            </label>
            <Link to="/forgot-password" className="auth-forgot-link">
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="auth-divider">
          <div className="auth-divider-line" />
          <span className="auth-divider-text">or</span>
          <div className="auth-divider-line" />
        </div>

        {/* Google Demo Login Button */}
        <button
          type="button"
          className="auth-google-btn"
          onClick={handleGoogleDemo}
        >
          <svg viewBox="0 0 24 24" width="16" height="16">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>Sign in with Google (Demo)</span>
        </button>

        {/* Footer Prompt */}
        <div className="auth-footer-prompt">
          <span>Don't have an account?</span>
          <Link to="/signup" className="auth-switch-link">
            Sign up
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
