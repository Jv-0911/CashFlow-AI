import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ShieldAlert, Sparkles, Terminal } from 'lucide-react';
import { DEMO_FORECAST } from '../../data/demo-fixtures';

export function InteractiveDemoPreview() {
  const navigate = useNavigate();
  const [horizon, setHorizon] = useState<number>(30);
  const [safetyBuffer, setSafetyBuffer] = useState<number>(1000); // in dollars

  const multiplier = horizon === 30 ? 1 : horizon === 60 ? 1.85 : 2.7;
  const projectedInflows = Math.round(18500 * multiplier);
  const projectedOutflows = Math.round(11200 * multiplier);
  const netEndingCash = Math.round(40000 + (projectedInflows - projectedOutflows));
  const isSafe = netEndingCash > safetyBuffer;

  return (
    <section id="interactive-demo" className="interactive-demo-section">
      <div className="interactive-demo-header">
        <div className="feature-pill pill-cyan">
          <Terminal size={14} />
          <span>Interactive Preview Engine</span>
        </div>
        <h2 className="demo-section-title">
          Experience The Financial Engine <br />
          <span className="gradient-text-blue">Before You Authenticate.</span>
        </h2>
        <p className="demo-section-desc">
          Test real-time calculation velocity with our deterministic model. Adjust horizon length
          and safety reserve thresholds to simulate immediate solvency verification.
        </p>
      </div>

      <div className="demo-console-box">
        <div className="demo-console-topbar">
          <div className="console-traffic-lights">
            <span className="light red" />
            <span className="light yellow" />
            <span className="light green" />
          </div>
          <span className="console-title">cashflow_deterministic_kernel.v2 [LIVE REPL]</span>
          <span className="console-tag">Zero Hallucinations</span>
        </div>

        <div className="demo-console-content">
          <div className="demo-control-panel">
            <div className="demo-control-item">
              <label htmlFor="horizon-select">Forecast Horizon Window</label>
              <div id="horizon-select" className="horizon-pills">
                {[30, 60, 90].map((h) => (
                  <button
                    key={h}
                    type="button"
                    className={`horizon-pill-btn ${horizon === h ? 'active' : ''}`}
                    onClick={() => setHorizon(h)}
                  >
                    {h} Days
                  </button>
                ))}
              </div>
            </div>

            <div className="demo-control-item">
              <label htmlFor="buffer-input">Configured Safety Floor ($ USD)</label>
              <div className="input-with-currency">
                <span>$</span>
                <input
                  id="buffer-input"
                  type="number"
                  value={safetyBuffer}
                  step="500"
                  min="500"
                  max="50000"
                  onChange={(e) => setSafetyBuffer(Number(e.target.value))}
                  className="demo-number-input"
                />
              </div>
            </div>

            <div className="demo-control-item">
              <label>API Contract Reference</label>
              <div className="contract-code-tag">
                <code>contracts/forecast-response.example.json</code>
              </div>
            </div>
          </div>

          <div className="demo-output-panel">
            <div className="output-row">
              <span className="output-label">Starting Cash Liquidity:</span>
              <span className="output-val font-mono">$40,000.00</span>
            </div>
            <div className="output-row">
              <span className="output-label">Projected Incoming Inflows:</span>
              <span className="output-val font-mono positive">+${projectedInflows.toLocaleString()}.00</span>
            </div>
            <div className="output-row">
              <span className="output-label">Projected Outgoing Expenses:</span>
              <span className="output-val font-mono negative">-${projectedOutflows.toLocaleString()}.00</span>
            </div>
            <div className="output-divider" />
            <div className="output-row highlight">
              <span className="output-label">Ending Solvency Projection:</span>
              <span className="output-val font-mono bold">${netEndingCash.toLocaleString()}.00</span>
            </div>

            <div className={`solvency-status-badge ${isSafe ? 'safe' : 'breached'}`}>
              {isSafe ? (
                <>
                  <CheckCircle2 size={16} />
                  <span>Reserve Intact: Ending balance exceeds ${safetyBuffer.toLocaleString()} floor.</span>
                </>
              ) : (
                <>
                  <ShieldAlert size={16} />
                  <span>Breach Detected: Recommended AI Rescue trigger ready.</span>
                </>
              )}
            </div>

            <button
              type="button"
              className="launch-full-app-btn"
              onClick={() => navigate('/login')}
            >
              <Sparkles size={16} />
              <span>Launch Full App With Your Accounts</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </div>

        <div className="demo-console-disclaimer">
          <span>{DEMO_FORECAST.disclaimer}</span>
        </div>
      </div>
    </section>
  );
}
