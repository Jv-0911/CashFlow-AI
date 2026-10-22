import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Building, Eye, EyeOff, Lock, Mail, User } from 'lucide-react';
import { AuthLayout } from './AuthLayout';

export function SignupPage() {
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const errs: Record<string, string> = {};

    if (!fullName.trim()) errs.fullName = 'Full name is required.';
    if (!businessName.trim()) errs.businessName = 'Business name is required.';
    if (!email.trim() || !email.includes('@')) errs.email = 'Valid email is required.';
    if (password.length < 8) errs.password = 'Password must be at least 8 characters.';
    if (password !== confirmPassword) errs.confirmPassword = 'Passwords do not match.';
    if (!agreeTerms) errs.agreeTerms = 'You must agree to the Terms of Service.';

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      // Navigate to verification screen with parameters
      navigate(
        `/verify-email?email=${encodeURIComponent(email)}&name=${encodeURIComponent(fullName)}&biz=${encodeURIComponent(businessName)}`
      );
    }, 500);
  };

  return (
    <AuthLayout>
      <div className="auth-card">
        {/* Header */}
        <div className="auth-avatar-header">
          <div className="auth-avatar-circle">
            <User size={24} color="#7896B0" />
          </div>
          <h1 className="auth-title">Create Account</h1>
          <p className="auth-subtitle">Start deterministic cash-flow intelligence</p>
        </div>

        {/* Form */}
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          {/* Full Name */}
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="name-input">
              Full Name
            </label>
            <div className="auth-input-wrapper">
              <User size={18} className="auth-input-icon" />
              <input
                id="name-input"
                type="text"
                className="auth-input"
                placeholder="Sarah Connor"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                required
              />
            </div>
            {errors.fullName && <span className="auth-field-error">{errors.fullName}</span>}
          </div>

          {/* Business Name */}
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="biz-input">
              Company / Venture Name
            </label>
            <div className="auth-input-wrapper">
              <Building size={18} className="auth-input-icon" />
              <input
                id="biz-input"
                type="text"
                className="auth-input"
                placeholder="Cyberdyne Systems"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                autoComplete="organization"
                required
              />
            </div>
            {errors.businessName && <span className="auth-field-error">{errors.businessName}</span>}
          </div>

          {/* Email */}
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="email-signup-input">
              Work Email
            </label>
            <div className="auth-input-wrapper">
              <Mail size={18} className="auth-input-icon" />
              <input
                id="email-signup-input"
                type="email"
                className="auth-input"
                placeholder="sarah@cyberdyne.io"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>
            {errors.email && <span className="auth-field-error">{errors.email}</span>}
          </div>

          {/* Password */}
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="pwd-signup-input">
              Password (min. 8 characters)
            </label>
            <div className="auth-input-wrapper">
              <Lock size={18} className="auth-input-icon" />
              <input
                id="pwd-signup-input"
                type={showPassword ? 'text' : 'password'}
                className="auth-input"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
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
            {errors.password && <span className="auth-field-error">{errors.password}</span>}
          </div>

          {/* Confirm Password */}
          <div className="auth-field-group">
            <label className="auth-label" htmlFor="confirm-pwd-input">
              Confirm Password
            </label>
            <div className="auth-input-wrapper">
              <Lock size={18} className="auth-input-icon" />
              <input
                id="confirm-pwd-input"
                type={showPassword ? 'text' : 'password'}
                className="auth-input"
                placeholder="••••••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </div>
            {errors.confirmPassword && <span className="auth-field-error">{errors.confirmPassword}</span>}
          </div>

          {/* Terms Checkbox */}
          <div className="auth-field-group">
            <label className="auth-remember-label">
              <input
                type="checkbox"
                className="auth-checkbox"
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
              />
              <span>I agree to the Terms of Service & Privacy Policy</span>
            </label>
            {errors.agreeTerms && <span className="auth-field-error">{errors.agreeTerms}</span>}
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span>Creating Account...</span>
            ) : (
              <>
                <span>Continue to Verification</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Footer Prompt */}
        <div className="auth-footer-prompt">
          <span>Already have an account?</span>
          <Link to="/login" className="auth-switch-link">
            Sign in
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
