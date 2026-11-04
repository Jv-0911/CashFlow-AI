import { useNavigate } from 'react-router-dom';
import { ArrowRight, ChevronDown, Shield, Sparkles, TrendingUp, Zap } from 'lucide-react';
import { NavBar } from './NavBar';
import { HeroScene } from './HeroScene';
import { FeatureSection } from './FeatureSection';
import { InteractiveDemoPreview } from './InteractiveDemoPreview';
import { Footer } from './Footer';
import '../../styles/landing.css';

export function LandingPage() {
  const navigate = useNavigate();

  const handleScrollToFeatures = () => {
    const el = document.getElementById('forecasting');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="landing-page-root">
      {/* Floating Glass Navigation */}
      <NavBar />

      {/* ---------------- 3D Cinematic Hero Section ---------------- */}
      <section className="landing-hero-section">
        {/* Three.js Financial Sculpture Canvas */}
        <HeroScene />

        {/* Hero Content Overlay */}
        <div className="landing-hero-content">
          <div className="hero-announcement-pill">
            <span className="pill-pulse" />
            <Sparkles size={14} className="pill-icon" />
            <span>CashFlow AI 2.0 • Deterministic Financial Intelligence</span>
          </div>

          <h1 className="hero-headline">
            Intelligent Cash-Flow <br />
            <span className="hero-headline-gradient">Forecasting & AI Recovery</span>
          </h1>

          <p className="hero-subtitle">
            Eliminate cash shortages before they occur. A unified financial engine that calculates
            runway in exact integer cents, simulates real-world stress scenarios, and synthesizes
            autonomous rescue plans with verified PayPal ledger settlements.
          </p>

          <div className="hero-cta-group">
            <button
              type="button"
              className="hero-primary-cta"
              onClick={() => navigate('/login')}
            >
              <span>Get Started Free</span>
              <ArrowRight size={18} />
            </button>

            <button
              type="button"
              className="hero-secondary-cta"
              onClick={handleScrollToFeatures}
            >
              <Zap size={16} />
              <span>Explore The Engine</span>
            </button>
          </div>

          {/* Trust Badges */}
          <div className="hero-trust-bar">
            <div className="trust-item">
              <Shield size={16} className="trust-icon" />
              <span>Zero-Hallucination Math</span>
            </div>
            <div className="trust-separator">•</div>
            <div className="trust-item">
              <TrendingUp size={16} className="trust-icon" />
              <span>Integer-Cent Precision</span>
            </div>
            <div className="trust-separator">•</div>
            <div className="trust-item">
              <Sparkles size={16} className="trust-icon" />
              <span>Evidence-Backed Recovery</span>
            </div>
          </div>
        </div>

        {/* Scroll Indicator */}
        <button
          type="button"
          className="hero-scroll-indicator"
          onClick={handleScrollToFeatures}
          aria-label="Scroll to feature details"
        >
          <span>Scroll to Explore</span>
          <ChevronDown size={16} className="scroll-arrow" />
        </button>
      </section>

      {/* ---------------- Scroll-Driven Feature Showcase ---------------- */}
      <FeatureSection />

      {/* ---------------- Live Interactive Demo Console ---------------- */}
      <InteractiveDemoPreview />

      {/* ---------------- Footer ---------------- */}
      <Footer />
    </div>
  );
}
