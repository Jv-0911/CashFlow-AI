import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { BarChart3, CreditCard, GitBranch, Settings, Sparkles } from 'lucide-react';
import { ThemeProvider, AuthProvider } from './context';

const LandingPage = lazy(() =>
  import('./features/landing/LandingPage').then((m) => ({ default: m.LandingPage }))
);
const LoginPage = lazy(() =>
  import('./features/auth/LoginPage').then((m) => ({ default: m.LoginPage }))
);
const SignupPage = lazy(() =>
  import('./features/auth/SignupPage').then((m) => ({ default: m.SignupPage }))
);
const VerifyEmailPage = lazy(() =>
  import('./features/auth/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage }))
);
const ForgotPasswordPage = lazy(() =>
  import('./features/auth/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage }))
);
const DashboardLayout = lazy(() =>
  import('./features/dashboard/DashboardLayout').then((m) => ({ default: m.DashboardLayout }))
);
const OverviewPage = lazy(() =>
  import('./features/dashboard/OverviewPage').then((m) => ({ default: m.OverviewPage }))
);
const ForecastPage = lazy(() =>
  import('./features/forecast/ForecastPage').then((m) => ({ default: m.ForecastPage }))
);
const ModularPagePlaceholder = lazy(() =>
  import('./features/dashboard/ModularPagePlaceholder').then((m) => ({ default: m.ModularPagePlaceholder }))
);

function PageLoadingFallback() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0B1018',
        color: '#9AA6B5',
        fontFamily: 'Inter, system-ui, sans-serif',
        fontSize: '13px',
      }}
    >
      <div
        style={{
          width: '28px',
          height: '28px',
          border: '2px solid rgba(120, 150, 176, 0.2)',
          borderTopColor: '#7896B0',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={<PageLoadingFallback />}>
            <Routes>
              {/* Landing Page */}
              <Route path="/" element={<LandingPage />} />

              {/* Authentication Suite */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />

              {/* Dashboard Shell & Overview (Milestone 4) */}
              <Route path="/dashboard" element={<DashboardLayout />}>
                <Route index element={<OverviewPage />} />
                <Route path="overview" element={<OverviewPage />} />
                <Route path="forecast" element={<ForecastPage />} />
                <Route
                  path="rescue"
                  element={
                    <ModularPagePlaceholder
                      title="AI Rescue Suite"
                      milestone="Milestone 6 Ahead"
                      description="Ranked recovery recommendations, gap-closure simulations, and PayPal invoice follow-ups to preserve liquidity without debt."
                      icon={Sparkles}
                    />
                  }
                />
                <Route
                  path="scenarios"
                  element={
                    <ModularPagePlaceholder
                      title="Scenario Simulation"
                      milestone="Milestone 7 Ahead"
                      description="Simulate what-if parameters: delayed receivables, hiring costs, inventory buffers, and unexpected vendor expenses."
                      icon={GitBranch}
                    />
                  }
                />
                <Route
                  path="payments"
                  element={
                    <ModularPagePlaceholder
                      title="Payments & Verified Ledger"
                      milestone="Milestone 8 Ahead"
                      description="Audit-grade ledger with PayPal Sandbox transaction verification, RFC-8785 canonical hashing, and status reconciliation."
                      icon={CreditCard}
                    />
                  }
                />
                <Route
                  path="analytics"
                  element={
                    <ModularPagePlaceholder
                      title="Cash Analytics & Historical Performance"
                      milestone="Milestone 9 Ahead"
                      description="In-depth burn rate analysis, collection cycles (DSO), variance against forecast, and category breakdowns."
                      icon={BarChart3}
                    />
                  }
                />
                <Route
                  path="settings"
                  element={
                    <ModularPagePlaceholder
                      title="Settings & Governance"
                      milestone="Configuration"
                      description="Manage safety reserve thresholds, notification alerts, currency preferences, and API keys."
                      icon={Settings}
                    />
                  }
                />
              </Route>

              {/* Wildcard Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
