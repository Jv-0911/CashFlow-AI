import { useState, useRef } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Info, MailCheck, RotateCcw } from 'lucide-react';
import { AuthLayout } from './AuthLayout';

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const emailParam = searchParams.get('email') || 'this workspace';

  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [verifying, setVerifying] = useState(false);
  const [resendStatus, setResendStatus] = useState<string | null>(null);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const handleDigitChange = (index: number, val: string) => {
    const cleanVal = val.replace(/\D/g, '').slice(-1);
    const newDigits = [...digits];
    newDigits[index] = cleanVal;
    setDigits(newDigits);

    if (cleanVal && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleVerify = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setVerifying(true);

    setTimeout(() => {
      // Email verification is not configured; it grants no session.
      setVerifying(false);
      navigate('/login');
    }, 700);
  };

  const handleResend = () => {
    setResendStatus('No email sent. Contact your administrator.');
    setTimeout(() => setResendStatus(null), 4000);
  };

  return (
    <AuthLayout>
      <div className="auth-card">
        {/* Header */}
        <div className="auth-avatar-header">
          <div className="auth-avatar-circle">
            <MailCheck size={26} color="#7896B0" />
          </div>
          <h1 className="auth-title">Verify Your Email</h1>
          <p className="auth-subtitle">
            Email verification is not configured for <br />
            <strong style={{ color: 'var(--text-primary)' }}>{emailParam}</strong>
          </p>
        </div>

        {/* Demo-versus-Real Transparency Notice */}
        <div className="auth-disclaimer-box" role="status">
          <Info size={16} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Demo Verification Status:</strong> Real SMTP delivery is disabled in this hackathon environment.
            No code grants access. Sign in with the privately configured administrator password.
          </div>
        </div>

        {/* 6-Digit Code Inputs */}
        <form onSubmit={handleVerify}>
          <div className="code-inputs-container">
            {digits.map((digit, idx) => (
              <input disabled
                key={idx}
                ref={(el) => { inputRefs.current[idx] = el; }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                className="code-digit-input"
                value={digit}
                onChange={(e) => handleDigitChange(idx, e.target.value)}
                onKeyDown={(e) => handleKeyDown(idx, e)}
                aria-label={`Digit ${idx + 1}`}
              />
            ))}
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={verifying}
          >
            {verifying ? (
              <span>Returning to sign-in...</span>
            ) : (
              <>
                <CheckCircle2 size={16} />
                <span>Verify & Launch Dashboard</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Resend simulated code */}
        <div style={{ textAlign: 'center' }}>
          {resendStatus ? (
            <span style={{ fontSize: '12px', color: '#34d399' }}>{resendStatus}</span>
          ) : (
            <button
              type="button"
              className="auth-forgot-link"
              onClick={handleResend}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '12px' }}
            >
              <RotateCcw size={13} />
              <span>Resend verification code</span>
            </button>
          )}
        </div>

        {/* Back Link */}
        <div className="auth-footer-prompt">
          <span>Wrong email?</span>
          <Link to="/signup" className="auth-switch-link">
            Change email
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
