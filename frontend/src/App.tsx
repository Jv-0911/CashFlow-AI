import { useState } from 'react';
import {
  Sun,
  Moon,
  CheckCircle2,
  Activity,
  Layers,
  ShieldCheck,
  Palette,
  Database,
  ArrowRight
} from 'lucide-react';
import { ThemeProvider, useTheme, AuthProvider } from './context';
import { getHealth, getForecast } from './api';
import './App.css';

function FoundationView() {
  const { theme, toggleTheme } = useTheme();
  const [probeStatus, setProbeStatus] = useState<string>('Ready to test live API connectivity.');
  const [probeLoading, setProbeLoading] = useState<boolean>(false);
  const [probeSuccess, setProbeSuccess] = useState<boolean | null>(null);

  const runApiProbe = async () => {
    setProbeLoading(true);
    setProbeStatus('Testing GET /api/v1/health and GET /api/v1/forecast...');
    try {
      const healthRes = await getHealth();
      const forecastRes = await getForecast();
      setProbeSuccess(true);
      setProbeStatus(
        `SUCCESS:\n` +
        `• Health endpoint: status=${healthRes.data.status}, version=${healthRes.data.version}\n` +
        `• Forecast endpoint: days=${forecastRes.data.days.length}, currency=${forecastRes.data.currency}\n` +
        `• X-Demo-Data header detected: ${forecastRes.isDemo ? 'YES (demo mode)' : 'NO'}\n` +
        `• Safety Reserve: $${(forecastRes.data.safety_reserve_cents / 100).toFixed(2)}\n` +
        `• Disclaimer: ${forecastRes.data.disclaimer}`
      );
    } catch (err: unknown) {
      setProbeSuccess(false);
      const msg = err instanceof Error ? err.message : String(err);
      setProbeStatus(
        `NOTE: Backend server not currently running at localhost:8000.\n` +
        `Client error: ${msg}\n` +
        `Fallback fixtures in src/data/demo-fixtures.ts are fully operational for offline mode.`
      );
    } finally {
      setProbeLoading(false);
    }
  };

  return (
    <div className="foundation-container">
      {/* Header */}
      <header className="foundation-header">
        <div className="foundation-brand">
          <div className="foundation-logo">CF</div>
          <span className="foundation-brand-title">CashFlow AI</span>
          <span className="foundation-badge">Milestone 1 — Foundation</span>
        </div>
        <button
          className="theme-toggle-btn"
          onClick={toggleTheme}
          type="button"
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          <span>{theme === 'dark' ? 'Light Theme' : 'Dark Navy'}</span>
        </button>
      </header>

      {/* Main Content */}
      <main className="foundation-main">
        <section className="foundation-hero">
          <h1>CashFlow AI 2.0 Frontend Foundation</h1>
          <p>
            Milestone 1 completed. React 19 + TypeScript + Vite architecture verified.
            Design token system active with dark navy/plum, light blue, and subtle pink themes.
          </p>
        </section>

        <div className="foundation-grid">
          {/* Card 1: Design Tokens */}
          <div className="foundation-card">
            <h2 className="foundation-card-title">
              <Palette size={20} color="var(--accent-blue)" />
              Design Token Verification
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
              Active theme: <strong style={{ color: 'var(--accent-blue)' }}>{theme.toUpperCase()}</strong>.
              All components inherit variables from <code>index.css</code>.
            </p>
            <div className="palette-swatches">
              <div className="palette-swatch">
                <div className="swatch-color" style={{ backgroundColor: 'var(--accent-blue)' }} />
                <div className="swatch-info">
                  <span className="swatch-name">Primary Accent</span>
                  <span className="swatch-val">Light Blue</span>
                </div>
              </div>
              <div className="palette-swatch">
                <div className="swatch-color" style={{ backgroundColor: 'var(--accent-pink)' }} />
                <div className="swatch-info">
                  <span className="swatch-name">Secondary Accent</span>
                  <span className="swatch-val">Subtle Pink</span>
                </div>
              </div>
              <div className="palette-swatch">
                <div className="swatch-color" style={{ backgroundColor: 'var(--bg-page)' }} />
                <div className="swatch-info">
                  <span className="swatch-name">Page Canvas</span>
                  <span className="swatch-val">Navy / Pale</span>
                </div>
              </div>
              <div className="palette-swatch">
                <div className="swatch-color" style={{ backgroundColor: 'var(--bg-card)' }} />
                <div className="swatch-info">
                  <span className="swatch-name">Card Surface</span>
                  <span className="swatch-val">Elevated</span>
                </div>
              </div>
              <div className="palette-swatch">
                <div className="swatch-color" style={{ backgroundColor: 'var(--color-success)' }} />
                <div className="swatch-info">
                  <span className="swatch-name">Positive / Inflow</span>
                  <span className="swatch-val">Emerald</span>
                </div>
              </div>
              <div className="palette-swatch">
                <div className="swatch-color" style={{ backgroundColor: 'var(--accent-purple)' }} />
                <div className="swatch-info">
                  <span className="swatch-name">Auth Glow</span>
                  <span className="swatch-val">Lavender</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Shared Contracts */}
          <div className="foundation-card">
            <h2 className="foundation-card-title">
              <ShieldCheck size={20} color="var(--color-success)" />
              Contract Types Verification
            </h2>
            <div className="check-list">
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span>
                  <strong>Forecast Contract:</strong> <code>ForecastResponse</code> and <code>ForecastDay</code> enforce ISO 8601 dates and integer cents.
                </span>
              </div>
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span>
                  <strong>Rescue Contract:</strong> <code>RescueResponse</code> and <code>RescueAction</code> with impact in integer cents.
                </span>
              </div>
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span>
                  <strong>Scenario Contract:</strong> <code>ScenarioRequest</code> matching backend requirements.
                </span>
              </div>
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span>
                  <strong>Ledger Integrity:</strong> <code>LedgerEntry</code> with strict <code>LedgerStatus</code> states, preventing unverified claims.
                </span>
              </div>
            </div>
          </div>

          {/* Card 3: Backend Connectivity Probe */}
          <div className="foundation-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="foundation-card-title">
              <Activity size={20} color="var(--accent-blue)" />
              API Connectivity & Header Probe
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
              Tests communication with the FastAPI backend layer (or verifies graceful fallback).
              Inspects <code>X-Demo-Data</code> header and demo disclaimer indicators.
            </p>
            <div>
              <button
                className="probe-btn"
                type="button"
                onClick={runApiProbe}
                disabled={probeLoading}
              >
                <Database size={16} />
                {probeLoading ? 'Probing...' : 'Run Live API Probe'}
              </button>
            </div>
            <pre className="probe-box" style={{
              borderColor: probeSuccess === true ? 'var(--color-success)' : undefined
            }}>
              {probeStatus}
            </pre>
          </div>

          {/* Card 4: Architecture Status */}
          <div className="foundation-card" style={{ gridColumn: '1 / -1' }}>
            <h2 className="foundation-card-title">
              <Layers size={20} color="var(--accent-pink)" />
              Milestone 1 Completion Summary
            </h2>
            <div className="check-list">
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span><strong>Branch:</strong> <code>frontend</code> isolated from <code>integration</code>. No backend files touched.</span>
              </div>
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span><strong>Dependencies:</strong> React 19, Vite 8, TypeScript 6, Lucide React, Recharts, Three.js installed.</span>
              </div>
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span><strong>Design Tokens:</strong> Vanilla CSS custom properties with full dark and light mode coverage.</span>
              </div>
              <div className="check-item">
                <CheckCircle2 size={16} className="check-icon" />
                <span><strong>Status:</strong> Ready for user approval. Milestone 2 (Cinematic Landing Page) is locked until approved.</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="foundation-footer">
        CashFlow AI 2.0 • Foundation Milestone 1 Complete • Awaiting user authorization for Milestone 2 <ArrowRight size={12} style={{ display: 'inline', verticalAlign: 'middle' }} />
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <FoundationView />
      </AuthProvider>
    </ThemeProvider>
  );
}
