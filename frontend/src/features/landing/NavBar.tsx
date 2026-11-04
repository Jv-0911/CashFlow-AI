import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sun, Moon, ArrowRight, Menu, X, Sparkles } from 'lucide-react';
import { useTheme } from '../../context';

export function NavBar() {
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { label: 'Forecasting', href: '#forecasting' },
    { label: 'AI Rescue', href: '#rescue' },
    { label: 'Scenarios', href: '#scenarios' },
    { label: 'PayPal Ledger', href: '#payments' },
    { label: 'Live Engine', href: '#interactive-demo' },
  ];

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    setMobileMenuOpen(false);
    const target = document.querySelector(href);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="landing-navbar-wrapper">
      <nav className="landing-navbar" aria-label="Main Navigation">
        {/* Brand Mark */}
        <a href="#" className="landing-brand" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
          <div className="landing-brand-logo">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="url(#cf-nav-grad)" />
              <defs>
                <linearGradient id="cf-nav-grad" x1="6" y1="2" x2="17" y2="21" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#38bdf8" />
                  <stop offset="1" stopColor="#f472b6" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span className="landing-brand-text">
            CashFlow <span className="landing-brand-ai">AI</span>
          </span>
          <span className="landing-version-pill">2.0</span>
        </a>

        {/* Desktop Navigation Links */}
        <div className="landing-nav-links">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="landing-nav-link"
              onClick={(e) => handleNavClick(e, link.href)}
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Right Actions: Theme Toggle, Sign In, Get Started */}
        <div className="landing-nav-actions">
          <button
            type="button"
            className="landing-theme-toggle"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          <button
            type="button"
            className="landing-signin-btn"
            onClick={() => navigate('/login')}
          >
            Sign In
          </button>

          <button
            type="button"
            className="landing-cta-btn"
            onClick={() => navigate('/login')}
          >
            <span>Get Started</span>
            <ArrowRight size={15} />
          </button>

          {/* Mobile Menu Trigger */}
          <button
            type="button"
            className="landing-mobile-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </nav>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="landing-mobile-drawer">
          <div className="landing-mobile-links">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="landing-mobile-link"
                onClick={(e) => handleNavClick(e, link.href)}
              >
                {link.label}
              </a>
            ))}
          </div>
          <div className="landing-mobile-actions">
            <button
              type="button"
              className="landing-mobile-cta"
              onClick={() => { setMobileMenuOpen(false); navigate('/login'); }}
            >
              <Sparkles size={16} />
              <span>Get Started Free</span>
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
