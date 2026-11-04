import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, Shield, Sparkles } from 'lucide-react';

const CURRENT_YEAR = new Date().getFullYear();

export function Footer() {
  const navigate = useNavigate();

  return (
    <footer className="landing-footer">
      <div className="landing-footer-inner">
        {/* Top CTA Banner */}
        <div className="footer-cta-card">
          <div className="footer-cta-content">
            <span className="footer-cta-pill">
              <Sparkles size={14} />
              <span>Next Generation Treasury Intelligence</span>
            </span>
            <h3 className="footer-cta-title">
              Ready to Protect Your Working Capital?
            </h3>
            <p className="footer-cta-desc">
              Experience zero-hallucination forecasting, autonomous rescue recommendations,
              and cryptographic ledger verification designed specifically for modern startups.
            </p>
          </div>
          <div className="footer-cta-action">
            <button
              type="button"
              className="footer-primary-btn"
              onClick={() => navigate('/login')}
            >
              <span>Get Started Now</span>
              <ArrowUpRight size={18} />
            </button>
          </div>
        </div>

        {/* Main Footer Links */}
        <div className="footer-links-grid">
          <div className="footer-brand-col">
            <div className="footer-brand">
              <div className="landing-brand-logo small">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="#38bdf8" />
                </svg>
              </div>
              <span className="footer-brand-name">CashFlow AI</span>
            </div>
            <p className="footer-brand-bio">
              Deterministic cash-flow forecasting & AI recovery engine for high-velocity teams.
            </p>
            <div className="footer-security-badge">
              <Shield size={14} />
              <span>RFC-8785 Canonical JSON Verified</span>
            </div>
          </div>

          <div className="footer-col">
            <h4 className="footer-col-title">Core Engine</h4>
            <ul className="footer-link-list">
              <li><a href="#forecasting">Deterministic Forecasting</a></li>
              <li><a href="#rescue">Autonomous AI Rescue</a></li>
              <li><a href="#scenarios">Scenario Stress Testing</a></li>
              <li><a href="#payments">PayPal Sandbox Ledger</a></li>
              <li><a href="#interactive-demo">Live Interactive REPL</a></li>
            </ul>
          </div>

          <div className="footer-col">
            <h4 className="footer-col-title">Architecture</h4>
            <ul className="footer-link-list">
              <li><span className="footer-text-link">Pydantic 2 Schemas</span></li>
              <li><span className="footer-text-link">FastAPI 0.1.0 Layer</span></li>
              <li><span className="footer-text-link">Three.js Visual Canvas</span></li>
              <li><span className="footer-text-link">Vite 8 + React 19 SPA</span></li>
              <li><span className="footer-text-link">Vanilla CSS Tokens</span></li>
            </ul>
          </div>

          <div className="footer-col">
            <h4 className="footer-col-title">Platform</h4>
            <ul className="footer-link-list">
              <li>
                <button type="button" className="footer-btn-link" onClick={() => navigate('/login')}>
                  Hackathon Demo Sign In
                </button>
              </li>
              <li>
                <a href="https://github.com/Jv-0911/CashFlow-AI" target="_blank" rel="noreferrer" className="footer-external-link">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                  <span>GitHub Repository</span>
                </a>
              </li>
              <li><span className="footer-text-link">API Specification (/docs)</span></li>
              <li><span className="footer-text-link">Status: Operational</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom Legal & Disclaimer */}
        <div className="footer-bottom-bar">
          <p className="footer-disclaimer">
            CashFlow AI is an intelligence prototype. All calculations conform strictly to shared contracts
            and integer-cent accounting. Not affiliated with real banking or financial advisory services.
          </p>
          <div className="footer-copyright">
            © {CURRENT_YEAR} CashFlow AI 2.0. All rights reserved.
          </div>
        </div>
      </div>
    </footer>
  );
}
