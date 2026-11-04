import { useState } from 'react';
import {
  TrendingUp,
  Sparkles,
  Sliders,
  ShieldCheck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowUpRight,
  ChevronRight
} from 'lucide-react';

export function FeatureSection() {
  // Interactive state for Scenario simulation demo
  const [delayedDays, setDelayedDays] = useState<number>(14);
  const [expenseCut, setExpenseCut] = useState<boolean>(true);

  // Computed scenario values based on interactive state
  const baseEndingBalance = 407000; // in cents ($4,070.00)
  const penaltyPerDay = 12500; // in cents
  const savings = expenseCut ? 35000 : 0;
  const projectedBalance = baseEndingBalance - (delayedDays * penaltyPerDay) + savings;
  const delta = projectedBalance - baseEndingBalance;

  return (
    <div className="landing-features-container">
      {/* ---------------- Pillar 1: Deterministic Forecasting ---------------- */}
      <section id="forecasting" className="landing-feature-row">
        <div className="feature-text-col">
          <div className="feature-pill">
            <TrendingUp size={14} />
            <span>Pillar 01 • Deterministic Forecasting</span>
          </div>
          <h2 className="feature-heading">
            Mathematical Precision.<br />
            <span className="gradient-text-blue">Zero Hallucinations.</span>
          </h2>
          <p className="feature-desc">
            Unlike generic AI chatbots that guess numbers, CashFlow AI separates business calculations
            from language intelligence. Every forecast is calculated in exact integer cents directly from
            audited bank receipts and recurring expenses.
          </p>
          <ul className="feature-benefit-list">
            <li>
              <CheckCircle2 size={18} className="feature-check-icon" />
              <span><strong>Integer-Cent Precision:</strong> Eliminates floating-point rounding errors.</span>
            </li>
            <li>
              <CheckCircle2 size={18} className="feature-check-icon" />
              <span><strong>Safety Reserve Thresholds:</strong> Automatic detection of first breach dates.</span>
            </li>
            <li>
              <CheckCircle2 size={18} className="feature-check-icon" />
              <span><strong>Multi-Horizon Projections:</strong> Real-time modeling for 30, 60, and 90-day cash cycles.</span>
            </li>
          </ul>
        </div>

        <div className="feature-visual-col">
          <div className="visual-card-glass">
            <div className="visual-card-header">
              <div className="visual-card-title">
                <span className="dot-indicator pulse" />
                <span>Live Horizon Projection (30 Days)</span>
              </div>
              <span className="badge-demo">Contract Verified</span>
            </div>

            <div className="forecast-stats-grid">
              <div className="forecast-stat-box">
                <span className="stat-label">Starting Cash</span>
                <span className="stat-val">$40,000.00</span>
                <span className="stat-sub positive">+12.4% vs last cycle</span>
              </div>
              <div className="forecast-stat-box">
                <span className="stat-label">Safety Reserve</span>
                <span className="stat-val warning">$10,000.00</span>
                <span className="stat-sub">Floor Threshold</span>
              </div>
              <div className="forecast-stat-box">
                <span className="stat-label">First Breach Date</span>
                <span className="stat-val safe">None Detected</span>
                <span className="stat-sub positive">100% Solvency</span>
              </div>
            </div>

            {/* Visual Mini Chart Simulation */}
            <div className="mini-chart-container">
              <div className="chart-bars">
                {[65, 72, 68, 85, 92, 78, 88, 95, 82, 90, 100, 94].map((height, idx) => (
                  <div key={idx} className="chart-bar-col">
                    <div
                      className={`chart-bar ${idx > 8 ? 'future' : ''}`}
                      style={{ height: `${height}%` }}
                    />
                    <span className="chart-label">W{Math.floor(idx / 3) + 1}</span>
                  </div>
                ))}
              </div>
              <div className="threshold-line">
                <span className="threshold-tag">Safety Floor $10K</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- Pillar 2: Autonomous AI Rescue ---------------- */}
      <section id="rescue" className="landing-feature-row reverse">
        <div className="feature-text-col">
          <div className="feature-pill pill-pink">
            <Sparkles size={14} />
            <span>Pillar 02 • Autonomous AI Rescue</span>
          </div>
          <h2 className="feature-heading">
            Ranked Recovery Actions<br />
            <span className="gradient-text-pink">Before Cash Dries Up.</span>
          </h2>
          <p className="feature-desc">
            When forecasted outflows threaten your minimum safety reserve, our reasoning engine evaluates
            every incoming receivable, vendor contract, and variable expense to propose ranked, high-impact
            rescue actions with transparent evidence tracing.
          </p>
          <ul className="feature-benefit-list">
            <li>
              <CheckCircle2 size={18} className="feature-check-icon pink" />
              <span><strong>Evidence-Backed Logic:</strong> Every recommendation links back to specific invoice IDs.</span>
            </li>
            <li>
              <CheckCircle2 size={18} className="feature-check-icon pink" />
              <span><strong>Calculated Impact:</strong> Immediate projected cash recovery displayed in verified dollar amounts.</span>
            </li>
            <li>
              <CheckCircle2 size={18} className="feature-check-icon pink" />
              <span><strong>Execution Ease:</strong> 1-click invoice dispatch reminders and payment re-routing.</span>
            </li>
          </ul>
        </div>

        <div className="feature-visual-col">
          <div className="visual-card-glass">
            <div className="visual-card-header">
              <div className="visual-card-title">
                <AlertTriangle size={16} className="text-pink" />
                <span>AI Rescue Strategy Console</span>
              </div>
              <span className="badge-risk-high">Risk: High (Averted)</span>
            </div>

            <div className="rescue-actions-stack">
              <div className="rescue-action-item priority">
                <div className="action-rank">#1</div>
                <div className="action-info">
                  <div className="action-title-row">
                    <span className="action-title">Accelerate Invoice #INV-2026-88</span>
                    <span className="action-impact">+$5,000.00</span>
                  </div>
                  <span className="action-meta">Evidence: txn_demo_001 • Apex Corp • 3 Days Overdue</span>
                </div>
                <ArrowUpRight size={16} className="action-arrow" />
              </div>

              <div className="rescue-action-item">
                <div className="action-rank">#2</div>
                <div className="action-info">
                  <div className="action-title-row">
                    <span className="action-title">Defer Non-Critical Cloud Cluster</span>
                    <span className="action-impact">+$1,450.00</span>
                  </div>
                  <span className="action-meta">Evidence: recurring_sub_41 • Discretionary Dev Tier</span>
                </div>
                <ChevronRight size={16} className="action-arrow" />
              </div>

              <div className="rescue-action-item">
                <div className="action-rank">#3</div>
                <div className="action-info">
                  <div className="action-title-row">
                    <span className="action-title">Renegotiate Supplier Term to Net-45</span>
                    <span className="action-impact">+$3,200.00</span>
                  </div>
                  <span className="action-meta">Evidence: po_vendor_992 • Extended Liquidity Window</span>
                </div>
                <ChevronRight size={16} className="action-arrow" />
              </div>
            </div>

            <div className="rescue-summary-footer">
              <span>Total Recoverable Liquidity:</span>
              <span className="rescue-total">+$9,650.00</span>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- Pillar 3: Scenario Simulation ---------------- */}
      <section id="scenarios" className="landing-feature-row">
        <div className="feature-text-col">
          <div className="feature-pill">
            <Sliders size={14} />
            <span>Pillar 03 • Scenario Simulator</span>
          </div>
          <h2 className="feature-heading">
            Simulate Shocks.<br />
            <span className="gradient-text-blue">Stress-Test Your Balance Sheet.</span>
          </h2>
          <p className="feature-desc">
            What happens if your largest customer delays their milestone by 14 days? Or if payroll surges
            by 15%? Interactive stress testing lets you toggle parameters in real time and observe the immediate
            runway delta.
          </p>
          <ul className="feature-benefit-list">
            <li>
              <CheckCircle2 size={18} className="feature-check-icon" />
              <span><strong>Instant Recomputation:</strong> Live updates without re-querying expensive databases.</span>
            </li>
            <li>
              <CheckCircle2 size={18} className="feature-check-icon" />
              <span><strong>Comparative Delta:</strong> Compare baseline balance against stressed scenario paths.</span>
            </li>
          </ul>
        </div>

        <div className="feature-visual-col">
          <div className="visual-card-glass interactive-simulator">
            <div className="visual-card-header">
              <div className="visual-card-title">
                <Sliders size={16} color="var(--accent-blue)" />
                <span>Interactive Stress Console (Try It)</span>
              </div>
              <span className="badge-demo">Live Simulator</span>
            </div>

            <div className="simulator-controls">
              <div className="control-group">
                <div className="control-label-row">
                  <span>Customer Payment Delay</span>
                  <span className="control-val">{delayedDays} Days</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="30"
                  value={delayedDays}
                  onChange={(e) => setDelayedDays(Number(e.target.value))}
                  className="scenario-slider"
                />
              </div>

              <div className="control-group-toggle">
                <span>Apply Discretionary Freeze (+$350.00)</span>
                <button
                  type="button"
                  className={`toggle-switch ${expenseCut ? 'active' : ''}`}
                  onClick={() => setExpenseCut(!expenseCut)}
                >
                  <div className="toggle-thumb" />
                </button>
              </div>
            </div>

            <div className="simulation-result-box">
              <div className="sim-metric">
                <span className="sim-label">Baseline Day 30</span>
                <span className="sim-val">${(baseEndingBalance / 100).toFixed(2)}</span>
              </div>
              <div className="sim-metric">
                <span className="sim-label">Simulated Ending Cash</span>
                <span className={`sim-val ${delta < 0 ? 'negative' : 'positive'}`}>
                  ${(projectedBalance / 100).toFixed(2)}
                </span>
              </div>
              <div className="sim-metric">
                <span className="sim-label">Net Difference</span>
                <span className={`sim-val badge-delta ${delta >= 0 ? 'positive' : 'negative'}`}>
                  {delta >= 0 ? '+' : '-'}${Math.abs(delta / 100).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- Pillar 4: Verified PayPal Payments & Ledger ---------------- */}
      <section id="payments" className="landing-feature-row reverse">
        <div className="feature-text-col">
          <div className="feature-pill pill-lavender">
            <ShieldCheck size={14} />
            <span>Pillar 04 • Verified PayPal Payments</span>
          </div>
          <h2 className="feature-heading">
            Provider-Verified Integrity.<br />
            <span className="gradient-text-purple">No Fabricated Settlements.</span>
          </h2>
          <p className="feature-desc">
            Financial honesty is built into the core contract. A payment is never labeled as completed
            simply because a button was clicked. Every settlement requires authoritative webhook proof
            from the PayPal Sandbox provider before updating the cash-flow ledger.
          </p>
          <ul className="feature-benefit-list">
            <li>
              <CheckCircle2 size={18} className="feature-check-icon purple" />
              <span><strong>Cryptographic Webhooks:</strong> Status moves from pending to verified only with PayPal confirmation.</span>
            </li>
            <li>
              <CheckCircle2 size={18} className="feature-check-icon purple" />
              <span><strong>Tamper-Proof Audit Log:</strong> Every ledger entry preserves invoice ID, provider, and ISO timestamp.</span>
            </li>
          </ul>
        </div>

        <div className="feature-visual-col">
          <div className="visual-card-glass">
            <div className="visual-card-header">
              <div className="visual-card-title">
                <ShieldCheck size={16} className="text-purple" />
                <span>Audited Ledger Stream</span>
              </div>
              <span className="badge-verified">PayPal Sandbox Active</span>
            </div>

            <div className="ledger-stream">
              <div className="ledger-row">
                <div className="ledger-badge-status verified">
                  <CheckCircle2 size={14} />
                  <span>verified_completed</span>
                </div>
                <div className="ledger-entry-details">
                  <span className="ledger-id">ledger_demo_001 • #INV-2026-01</span>
                  <span className="ledger-provider">Provider: paypal_sandbox</span>
                </div>
                <span className="ledger-amount positive">+$500.00</span>
              </div>

              <div className="ledger-row">
                <div className="ledger-badge-status pending">
                  <Clock size={14} />
                  <span>pending_verification</span>
                </div>
                <div className="ledger-entry-details">
                  <span className="ledger-id">ledger_demo_002 • #INV-2026-02</span>
                  <span className="ledger-provider">Awaiting settlement webhook</span>
                </div>
                <span className="ledger-amount">+$1,250.00</span>
              </div>

              <div className="ledger-row">
                <div className="ledger-badge-status verified">
                  <CheckCircle2 size={14} />
                  <span>verified_completed</span>
                </div>
                <div className="ledger-entry-details">
                  <span className="ledger-id">ledger_demo_003 • #EXP-TAX-09</span>
                  <span className="ledger-provider">Automated Tax Outflow</span>
                </div>
                <span className="ledger-amount negative">-$750.00</span>
              </div>
            </div>

            <div className="ledger-audit-footer">
              <span>Integrity Standard: RFC-8785 JSON canonicalization active</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
