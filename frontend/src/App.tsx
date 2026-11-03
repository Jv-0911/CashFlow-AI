import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import {
  ApiError,
  dashboardSchema,
  dayLabel,
  entrySchema,
  ledgerSchema,
  money,
  request,
  rescueSchema,
  scenarioSchema,
  sessionSchema,
} from "./api";
import type {
  Dashboard,
  Entry,
  Forecast,
  Ledger,
  Rescue,
  Scenario,
  Session,
} from "./api";

type Page = "Overview" | "Forecast" | "What-if lab" | "Recovery" | "Ledger";
const pages: Page[] = [
  "Overview",
  "Forecast",
  "What-if lab",
  "Recovery",
  "Ledger",
];
const symbols = ["◈", "↗", "⇄", "✧", "▤"];
const captions: Record<Page, string> = {
  Overview: "Your next move, in focus.",
  Forecast: "See what’s around the corner.",
  "What-if lab": "Explore a different tomorrow.",
  Recovery: "Turn insight into a next step.",
  Ledger: "Every step. A clear record.",
};
function Badge({ value }: { value: string }) {
  return (
    <span
      className={
        "badge " +
        (value === "VERIFIED_PAID"
          ? "verified"
          : value === "PROPOSED"
            ? "neutral"
            : "pending")
      }
    >
      {value.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}
function Chart({
  forecast,
  comparison,
}: {
  forecast: Forecast;
  comparison?: Scenario | null;
}) {
  const values = forecast.days.map((d) => d.closing_balance_cents);
  const extra =
    comparison?.daily_differences.map(
      (d) => d.scenario_closing_balance_cents,
    ) ?? [];
  const low = Math.min(0, ...values, ...extra),
    high = Math.max(forecast.safety_reserve_cents, ...values, ...extra) * 1.15;
  const x = (i: number) => 70 + (i * 790) / Math.max(values.length - 1, 1),
    y = (n: number) => 245 - ((n - low) / (high - low || 1)) * 210;
  const points = values.map((n, i) => `${x(i)},${y(n)}`).join(" ");
  return (
    <div className="chart-wrap">
      <svg
        viewBox="0 0 900 290"
        role="img"
        aria-label="Daily projected closing cash compared with the safety reserve"
      >
        {[0, 1, 2, 3].map((i) => {
          const n = low + ((high - low) * i) / 3;
          return (
            <g key={i}>
              <line x1="70" x2="860" y1={y(n)} y2={y(n)} className="gridline" />
              <text x="58" y={y(n) + 4} textAnchor="end" className="axis">
                {money(Math.round(n))}
              </text>
            </g>
          );
        })}
        <polygon
          points={`70,245 ${points} ${x(values.length - 1)},245`}
          className="chart-fill"
        />
        <line
          x1="70"
          x2="860"
          y1={y(forecast.safety_reserve_cents)}
          y2={y(forecast.safety_reserve_cents)}
          className="reserve-line"
        />
        <polyline points={points} className="cash-line" />
        {extra.length > 0 && (
          <polyline
            points={extra.map((n, i) => `${x(i)},${y(n)}`).join(" ")}
            className="scenario-line"
          />
        )}
        {values.map((n, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(n)} r="3" className="cash-dot">
              <title>
                {dayLabel(forecast.days[i].date)}: {money(n)}
              </title>
            </circle>
            {(i === 0 || i === values.length - 1 || i % 3 === 0) && (
              <text x={x(i)} y="275" textAnchor="middle" className="axis">
                {dayLabel(forecast.days[i].date)}
              </text>
            )}
          </g>
        ))}
      </svg>
      <div className="legend">
        <span>
          <i className="green-dot" />
          Projected closing cash
        </span>
        <span>
          <i className="amber-dot" />
          Safety reserve
        </span>
        {comparison && (
          <span>
            <i className="blue-dot" />
            Hypothetical scenario
          </span>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("Overview");
  const [session, setSession] = useState<Session | null>(null);
  const [data, setData] = useState<Dashboard | null>(null);
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [rescue, setRescue] = useState<Rescue | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [horizon, setHorizon] = useState(14);
  const [event, setEvent] = useState("expense_payroll");
  const [delay, setDelay] = useState(7);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [password, setPassword] = useState("");
  const [approval, setApproval] = useState<Entry | null>(null);
  const [confirm, setConfirm] = useState(false);
  const generation = useRef(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const csrf = session?.csrf_token;
  const canWrite = !!session?.authenticated;
  const authorized = !session?.password_configured || canWrite;

  async function load(days = horizon) {
    const version = ++generation.current;
    setLoading(true);
    setError("");
    setData(null);
    setLedger(null);
    setScenario(null);
    setRescue(null);
    try {
      const s = await request("/session", sessionSchema);
      if (version !== generation.current) return;
      setSession(s);
      if (s.password_configured && !s.authenticated) return;
      const d = await request(
        "/dashboard?horizon_days=" + days,
        dashboardSchema,
      );
      const l = s.authenticated ? await request("/ledger", ledgerSchema) : null;
      if (version === generation.current) {
        setData(d);
        setLedger(l);
      }
    } catch (e) {
      if (version === generation.current)
        setError(
          e instanceof Error ? e.message : "Unable to load the dashboard.",
        );
    } finally {
      if (version === generation.current) setLoading(false);
    }
  }
  useEffect(() => {
    void load(horizon);
    return () => {
      generation.current++;
    };
  }, [horizon]);
  useEffect(() => {
    if (approval) dialog.current?.showModal();
    else dialog.current?.close();
  }, [approval]);
  async function act(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The action could not be completed.",
      );
      if (e instanceof ApiError && e.status === 401) {
        setData(null);
        setLedger(null);
        setSession((s) =>
          s ? { ...s, authenticated: false, csrf_token: null } : s,
        );
      }
    } finally {
      setBusy(false);
    }
  }
  async function paymentAction(
    entry: Entry,
    command: "create" | "send" | "verify",
  ) {
    const path =
      command === "create"
        ? "/invoices"
        : command === "send"
          ? `/invoices/${entry.entry_id}/send`
          : `/payments/${entry.entry_id}/verify`;
    await act(async () => {
      await request(path, entrySchema, {
        method: "POST",
        csrf,
        body: command === "create" ? { entry_id: entry.entry_id } : undefined,
      });
      await load();
      setNotice(
        "Ledger refreshed from the service. Only verified PayPal evidence counts as recovered cash.",
      );
    });
  }
  function controls(entry: Entry) {
    if (entry.status === "PROPOSED")
      return (
        <button
          className="small"
          disabled={busy}
          onClick={() => {
            setConfirm(false);
            setApproval(entry);
          }}
        >
          Review approval
        </button>
      );
    if (entry.status === "APPROVED")
      return (
        <button
          className="small"
          disabled={busy || !data?.payments_enabled}
          onClick={() => void paymentAction(entry, "create")}
        >
          Create Sandbox draft
        </button>
      );
    if (entry.status === "INVOICE_DRAFTED")
      return (
        <button
          className="small"
          disabled={busy || !data?.payments_enabled}
          onClick={() => void paymentAction(entry, "send")}
        >
          Send Sandbox invoice
        </button>
      );
    if (!["CANCELLED", "FAILED", "REFUNDED"].includes(entry.status))
      return (
        <button
          className="small secondary"
          disabled={busy || !data?.payments_enabled}
          onClick={() => void paymentAction(entry, "verify")}
        >
          Verify with PayPal
        </button>
      );
    return <span className="muted">Review required</span>;
  }
  const f = data?.forecast;
  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="CashFlow AI home">
          <span className="brand-mark">↗</span>cashflow
          <span className="brand-ai">AI</span>
        </a>
        <p className="workspace-label">YOUR WORKSPACE</p>
        <nav aria-label="Main navigation">
          {pages.map((p, i) => (
            <button
              key={p}
              aria-label={p}
              className={page === p ? "nav-item active" : "nav-item"}
              onClick={() => setPage(p)}
              aria-current={page === p ? "page" : undefined}
            >
              <span>{symbols[i]}</span>
              {p}
              {p === "Recovery" && <small>AI</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox-status">
            <i />
            PayPal Sandbox only
          </div>
          <p>
            Clear forecasts.
            <br />
            Considered decisions.
          </p>
          <div className="profile">
            <span>JS</span>
            <div>
              Juniper Studio<small>Demo workspace · USD</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="crumb">
            Workspace <span>/</span> {page}
          </div>
          <div className="top-actions">
            <span className="demo-pill">SYNTHETIC DEMO</span>
            {canWrite && (
              <button
                className="text-button"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    await request(
                      "/session",
                      z.object({ authenticated: z.literal(false) }),
                      { method: "DELETE", csrf },
                    );
                    await load();
                  })
                }
              >
                Sign out
              </button>
            )}
            <span className="avatar">JS</span>
          </div>
        </header>
        <main id="main-content">
          <div className="heading">
            <div>
              <p className="eyebrow">CASHFLOW INTELLIGENCE</p>
              <h1>
                {page === "Overview" ? "A clearer view of your cash." : page}
              </h1>
              <p>{captions[page]}</p>
            </div>
            <div className="heading-actions">
              <label className="sr-only" htmlFor="horizon">
                Forecast horizon
              </label>
              <select
                id="horizon"
                value={horizon}
                disabled={busy || loading}
                onChange={(e) => setHorizon(Number(e.target.value))}
              >
                <option value={7}>Next 7 days</option>
                <option value={14}>Next 14 days</option>
                <option value={30}>Next 30 days</option>
              </select>
              <button
                className="secondary"
                disabled={loading || busy}
                onClick={() => void load()}
              >
                ↻ Refresh
              </button>
            </div>
          </div>
          {error && (
            <div role="alert" className="alert error">
              <strong>We couldn’t complete that request.</strong>
              <p>{error}</p>
              <button
                className="small secondary"
                onClick={() => void load()}
                disabled={busy || loading}
              >
                Refresh safely
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              {notice}
            </div>
          )}
          {loading && (
            <div className="empty" role="status">
              <div className="spinner" />
              Loading your workspace…
            </div>
          )}
          {!loading && session && !authorized && (
            <section className="card login">
              <span className="icon-block">◇</span>
              <h2>Welcome to your workspace</h2>
              <p>
                Sign in with the administrator password configured privately on
                this server.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void act(async () => {
                    await request(
                      "/session",
                      z.object({
                        authenticated: z.literal(true),
                        csrf_token: z.string(),
                      }),
                      { method: "POST", body: { password } },
                    );
                    setPassword("");
                    await load();
                  });
                }}
              >
                <label htmlFor="password">Administrator password</label>
                <input
                  autoComplete="current-password"
                  id="password"
                  type="password"
                  maxLength={256}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button disabled={busy}>
                  {busy ? "Signing in…" : "Sign in securely"}
                </button>
              </form>
            </section>
          )}
          {!loading && data && f && (
            <>
              <div className="demo-notice">
                <span>ⓘ</span>
                <p>
                  Fictional business data as of {dayLabel(data.as_of_date)},
                  2026. Forecasts are projections.{" "}
                  {session?.read_only_demo
                    ? "Read-only mode: administrator access is not configured."
                    : "Ledger actions are limited to this demo business."}
                </p>
              </div>
              {(page === "Overview" || page === "Forecast") && (
                <>
                  <div className="metrics">
                    <article className="metric">
                      <p>
                        Opening cash <span>DEMO</span>
                      </p>
                      <strong>{money(f.days[0].opening_balance_cents)}</strong>
                      <small>Fictional opening snapshot</small>
                    </article>
                    <article className="metric">
                      <p>Safety reserve</p>
                      <strong>{money(f.safety_reserve_cents)}</strong>
                      <small>Your planning threshold</small>
                    </article>
                    <article className="metric">
                      <p>Lowest projected cash</p>
                      <strong>
                        {money(
                          Math.min(
                            ...f.days.map((d) => d.closing_balance_cents),
                          ),
                        )}
                      </strong>
                      <small>Across the next {horizon} days</small>
                    </article>
                    <article className="metric accent">
                      <p>Verified recovered cash</p>
                      <strong>
                        {data.recovered_cash === null
                          ? "—"
                          : money(data.recovered_cash)}
                      </strong>
                      <small>
                        {data.recovered_cash === null
                          ? "Sign in to view the ledger"
                          : "PayPal-verified entries only"}
                      </small>
                    </article>
                  </div>
                  <section className="card">
                    <div className="section-heading">
                      <div>
                        <h2>Cash flow outlook</h2>
                        <p>Expected receipts and expenses, day by day</p>
                      </div>
                      <span className="badge neutral">
                        {horizon}-day projection
                      </span>
                    </div>
                    <Chart forecast={f} />
                    {f.first_reserve_breach_date ? (
                      <div className="risk-strip">
                        <span>↘</span>
                        <p>
                          <strong>
                            Reserve pressure from{" "}
                            {dayLabel(f.first_reserve_breach_date)}
                          </strong>
                          <br />
                          Your projected cash falls below your safety reserve.
                          Explore your options early.
                        </p>
                        <button
                          className="small secondary"
                          onClick={() => setPage("Recovery")}
                        >
                          Explore recovery →
                        </button>
                      </div>
                    ) : (
                      <div className="risk-strip safe">
                        <p>
                          No projected reserve breach in this window. Expected
                          receipts are still uncertain.
                        </p>
                      </div>
                    )}
                  </section>
                </>
              )}
              {page === "Overview" && (
                <div className="two-col">
                  <section className="card">
                    <div className="section-heading">
                      <h2>Upcoming commitments</h2>
                      <span className="muted">Scheduled</span>
                    </div>
                    {data.expenses.map((e) => (
                      <div className="commitment" key={e.id}>
                        <span className="date-box">{dayLabel(e.date)}</span>
                        <div>
                          <strong>{e.label}</strong>
                          <small>
                            {e.discretionary
                              ? "Discretionary · reviewable"
                              : "Planned obligation"}
                          </small>
                        </div>
                        <strong>{money(e.amount_cents)}</strong>
                      </div>
                    ))}
                    <button
                      className="text-button arrow"
                      onClick={() => setPage("What-if lab")}
                    >
                      Test a timing change →
                    </button>
                  </section>
                  <section className="card insight">
                    <span className="eyebrow">YOUR NEXT STEP</span>
                    <h2>A plan before a shortfall.</h2>
                    <p>
                      Understand the pressure behind your forecast, review
                      overdue receivables, and choose an action with the
                      evidence in view.
                    </p>
                    <button onClick={() => setPage("Recovery")}>
                      Explore recovery options <span>→</span>
                    </button>
                    <small>Recommendations never execute payments.</small>
                  </section>
                </div>
              )}
              {page === "Forecast" && (
                <section className="card">
                  <h2>Daily forecast details</h2>
                  <p className="muted">
                    All values in USD. Receipts and expenses are projected.
                  </p>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Opening</th>
                          <th>Receipts</th>
                          <th>Expenses</th>
                          <th>Closing</th>
                        </tr>
                      </thead>
                      <tbody>
                        {f.days.map((d) => (
                          <tr key={d.date}>
                            <td>{dayLabel(d.date)}</td>
                            <td>{money(d.opening_balance_cents)}</td>
                            <td>{money(d.receipts_cents)}</td>
                            <td>{money(d.expenses_cents)}</td>
                            <td
                              className={
                                d.closing_balance_cents < f.safety_reserve_cents
                                  ? "warning-text"
                                  : ""
                              }
                            >
                              {money(d.closing_balance_cents)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="footnote">
                    Assumptions: historical daily activity continues;
                    receivables arrive on planned dates; scheduled obligations
                    occur as entered. These expectations are not payment
                    evidence.
                  </p>
                </section>
              )}
              {page === "What-if lab" && (
                <>
                  <section className="card">
                    <div className="section-heading">
                      <div>
                        <h2>Give your cash a little more room</h2>
                        <p>
                          Simulate a later expense date. No account or payment
                          is changed.
                        </p>
                      </div>
                      <span className="badge neutral">Hypothetical</span>
                    </div>
                    <form
                      className="scenario-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        setScenario(null);
                        void act(async () =>
                          setScenario(
                            await request("/scenarios", scenarioSchema, {
                              method: "POST",
                              csrf,
                              body: {
                                event_id: event,
                                delay_days: delay,
                                horizon_days: horizon,
                              },
                            }),
                          ),
                        );
                      }}
                    >
                      <label>
                        Scheduled expense
                        <select
                          value={event}
                          onChange={(e) => {
                            setEvent(e.target.value);
                            setScenario(null);
                          }}
                        >
                          {data.expenses.map((e) => (
                            <option key={e.id} value={e.id}>
                              {e.label} · {money(e.amount_cents)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Delay by
                        <select
                          value={delay}
                          onChange={(e) => {
                            setDelay(Number(e.target.value));
                            setScenario(null);
                          }}
                        >
                          {[3, 7, 14].map((n) => (
                            <option key={n} value={n}>
                              {n} days
                            </option>
                          ))}
                        </select>
                      </label>
                      <button disabled={busy}>
                        {busy ? "Calculating…" : "Run scenario →"}
                      </button>
                    </form>
                    <p className="footnote">
                      Assumes the payee explicitly agrees. A date outside the
                      forecast window shifts the obligation beyond this view; it
                      does not remove it.
                    </p>
                  </section>
                  {scenario && (
                    <section className="card" aria-live="polite">
                      <h2>Baseline vs. your scenario</h2>
                      <div className="scenario-summary">
                        <div>
                          <span>Baseline minimum</span>
                          <strong>
                            {money(
                              scenario.baseline_minimum_cash_balance_cents,
                            )}
                          </strong>
                          <small>
                            Reserve breach:{" "}
                            {scenario.baseline_shortage_date
                              ? dayLabel(scenario.baseline_shortage_date)
                              : "None in window"}
                          </small>
                        </div>
                        <div>
                          <span>Scenario minimum</span>
                          <strong>
                            {money(
                              scenario.scenario_minimum_cash_balance_cents,
                            )}
                          </strong>
                          <small>
                            Reserve breach:{" "}
                            {scenario.scenario_shortage_date
                              ? dayLabel(scenario.scenario_shortage_date)
                              : "None in window"}
                          </small>
                        </div>
                      </div>
                      <Chart forecast={f} comparison={scenario} />
                      {scenario.assumptions.map((a, i) => (
                        <p key={i} className="footnote">
                          {a}
                        </p>
                      ))}
                      <details>
                        <summary>Calculation limitations</summary>
                        {scenario.limitations.map((a, i) => (
                          <p key={i}>{a}</p>
                        ))}
                      </details>
                    </section>
                  )}
                </>
              )}
              {page === "Recovery" && (
                <>
                  <section className="card">
                    <div className="section-heading">
                      <div>
                        <h2>Evidence before action</h2>
                        <p>
                          Recommendations from your forecast, expenses, and
                          eligible receivables.
                        </p>
                      </div>
                      <button
                        disabled={busy}
                        onClick={() => {
                          setRescue(null);
                          void act(async () =>
                            setRescue(
                              await request(
                                "/rescue/analyze?horizon_days=" + horizon,
                                rescueSchema,
                                { method: "POST", csrf },
                              ),
                            ),
                          );
                        }}
                      >
                        {busy ? "Analyzing…" : "Analyze recovery ✧"}
                      </button>
                    </div>
                    {rescue ? (
                      <div aria-live="polite">
                        <span className="badge neutral">
                          {rescue.source === "deterministic"
                            ? "Deterministic analysis · no AI provider"
                            : "AI-assisted explanation"}
                        </span>
                        <p className="analysis-summary">{rescue.summary}</p>
                        {rescue.integration_warnings.map((w, i) => (
                          <p className="alert" key={i}>
                            {w}
                          </p>
                        ))}
                        <div className="action-grid">
                          {rescue.recommended_actions.map((a, i) => (
                            <article className="action-card" key={a.action_id}>
                              <span className="action-rank">
                                {String(i + 1).padStart(2, "0")}
                              </span>
                              <h3>{a.title}</h3>
                              <p>{a.explanation}</p>
                              <strong>
                                {a.estimated_impact_cents === null
                                  ? "Impact not quantified"
                                  : money(a.estimated_impact_cents)}
                              </strong>
                              <small>
                                Estimated exposure · not additional cash
                              </small>
                              <details>
                                <summary>Evidence & assumptions</summary>
                                <p className="evidence">
                                  {a.evidence_ids.join(", ")}
                                </p>
                                {a.assumptions.map((v, j) => (
                                  <p key={j}>{v}</p>
                                ))}
                              </details>
                            </article>
                          ))}
                        </div>
                        {rescue.recommended_actions.length === 0 && (
                          <p>No eligible recovery actions were identified.</p>
                        )}
                      </div>
                    ) : (
                      <div className="empty compact">
                        Run an analysis to see ranked actions and their
                        supporting evidence.
                      </div>
                    )}
                  </section>
                  <section className="card">
                    <h2>Receivables to review</h2>
                    <p className="muted">
                      Preparing an action only adds a proposal. Approval,
                      invoice creation, sending, and verification are separate
                      steps.
                    </p>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Customer / work</th>
                            <th>Due</th>
                            <th>Amount</th>
                            <th>Recovery action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.receivables.map((r) => (
                            <tr key={r.id}>
                              <td>
                                <strong>{r.customer}</strong>
                                <small>{r.description}</small>
                              </td>
                              <td>
                                {dayLabel(r.due_date)}
                                {r.due_date < data.as_of_date && (
                                  <small className="warning-text">
                                    Overdue
                                  </small>
                                )}
                              </td>
                              <td>{money(r.amount_cents)}</td>
                              <td>
                                {r.ledger_entry ? (
                                  <div className="cell-actions">
                                    <Badge value={r.ledger_entry.status} />
                                    {controls(r.ledger_entry)}
                                  </div>
                                ) : (
                                  <button
                                    className="small"
                                    disabled={busy || !canWrite}
                                    onClick={() =>
                                      void act(async () => {
                                        await request(
                                          "/ledger/proposals",
                                          entrySchema,
                                          {
                                            method: "POST",
                                            csrf,
                                            body: { receivable_id: r.id },
                                          },
                                        );
                                        await load();
                                        setNotice(
                                          "Proposal recorded. No invoice was created or sent. Review it in the ledger.",
                                        );
                                      })
                                    }
                                  >
                                    Prepare action
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!canWrite && (
                      <p className="footnote">
                        Administrator sign-in is required to prepare recovery
                        actions.
                      </p>
                    )}
                  </section>
                </>
              )}
              {page === "Ledger" && (
                <section className="card">
                  <div className="section-heading">
                    <div>
                      <h2>Recovery ledger</h2>
                      <p>
                        An append-only record of proposals, approvals, and
                        provider-verified outcomes.
                      </p>
                    </div>
                    <button
                      className="small secondary"
                      disabled={busy || !canWrite || !data.payments_enabled}
                      onClick={() =>
                        void act(async () => {
                          const result = await request(
                            "/payments/reconcile",
                            z.object({
                              results: z.array(
                                z.object({
                                  entry_id: z.string(),
                                  status: z.string(),
                                  error_code: z.string().nullable(),
                                }),
                              ),
                            }),
                            { method: "POST", csrf },
                          );
                          await load();
                          setNotice(
                            result.results.some((r) => r.error_code)
                              ? "Reconciliation needs attention. Last known states were retained; inspect provider configuration and the recovery runbook."
                              : "Reconciliation finished. Ledger observations have been refreshed.",
                          );
                        })
                      }
                    >
                      Reconcile with PayPal
                    </button>
                  </div>
                  {!data.payments_enabled && (
                    <div className="alert">
                      PayPal is not configured. Draft, send, and verification
                      actions are disabled. No payment completion is simulated.
                    </div>
                  )}
                  {!canWrite ? (
                    <div className="empty">
                      The ledger requires administrator sign-in. Configure
                      access privately, then reload.
                    </div>
                  ) : ledger?.entries.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Entry / updated</th>
                            <th>Amount</th>
                            <th>Status / provider</th>
                            <th>Next step</th>
                          </tr>
                        </thead>
                        <tbody>
                          {ledger.entries.map((e) => (
                            <tr key={e.entry_id}>
                              <td>
                                <code>{e.entry_id.slice(0, 18)}…</code>
                                <small>
                                  {new Date(e.updated_at).toLocaleString()}
                                </small>
                                {e.invoice_url && <small><a href={e.invoice_url} target="_blank" rel="noopener noreferrer">View Sandbox invoice ↗</a></small>}
                                {e.verified_at && (
                                  <small>
                                    Verified:{" "}
                                    {new Date(e.verified_at).toLocaleString()}
                                  </small>
                                )}
                              </td>
                              <td>{money(e.amount_cents)}</td>
                              <td>
                                <Badge value={e.status} />
                                <small>
                                  {e.provider_status ??
                                    "No provider observation"}
                                </small>
                              </td>
                              <td>{controls(e)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty">
                      <span className="icon-block">▤</span>
                      <h3>Your record starts here</h3>
                      <p>
                        Prepare a recovery action to add the first proposal.
                      </p>
                      <button
                        className="secondary"
                        onClick={() => setPage("Recovery")}
                      >
                        Review receivables →
                      </button>
                    </div>
                  )}
                  <p className="footnote">
                    Only VERIFIED_PAID entries contribute to recovered cash.
                    Pending, partial, offline-marked, failed, and refunded
                    entries do not.
                  </p>
                </section>
              )}
              <footer>
                {data.notice}
                <span>CashFlow AI · Built for better decisions</span>
              </footer>
            </>
          )}
        </main>
      </div>
      <dialog
        ref={dialog}
        onCancel={() => setApproval(null)}
        className="approval-dialog"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!approval || !confirm) return;
            const item = approval;
            void act(async () => {
              await request(
                "/ledger/" + item.entry_id + "/approve",
                entrySchema,
                {
                  method: "POST",
                  csrf,
                  body: { expected_sequence: item.sequence, confirmed: true },
                },
              );
              setApproval(null);
              await load();
              setNotice(
                "Human approval recorded. Create and send remain separate actions.",
              );
            });
          }}
        >
          <span className="eyebrow">HUMAN APPROVAL</span>
          <h2>Approve this recovery invoice?</h2>
          <p className="approval-amount">
            {approval && money(approval.amount_cents)} <small>USD</small>
          </p>
          <p>
            Recipient: the Sandbox test payer configured privately by the server
            administrator. This approval records your identity and authorizes
            the later draft and send steps.
          </p>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={confirm}
              onChange={(e) => setConfirm(e.target.checked)}
            />
            I have reviewed the amount and configured test recipient and
            explicitly approve.
          </label>
          {error && (
            <p role="alert" className="alert error">
              {error}
            </p>
          )}
          <div className="dialog-actions">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => setApproval(null)}
            >
              Cancel
            </button>
            <button disabled={!confirm || busy}>Record approval</button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
