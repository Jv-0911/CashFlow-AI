import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, AuthProvider, CustomizationProvider } from './context';

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
const RescuePage = lazy(() =>
  import('./features/rescue/RescuePage').then((m) => ({ default: m.RescuePage }))
);
const ScenarioPage = lazy(() =>
  import('./features/scenarios/ScenarioPage').then((m) => ({ default: m.ScenarioPage }))
);
const PaymentsLedgerPage = lazy(() =>
  import('./features/ledger/PaymentsLedgerPage').then((m) => ({ default: m.PaymentsLedgerPage }))
);
const AnalyticsPage = lazy(() =>
  import('./features/analytics/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage }))
);
const SettingsPage = lazy(() =>
  import('./features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage }))
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
        <CustomizationProvider>
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
                  <Route path="rescue" element={<RescuePage />} />
                  <Route path="scenarios" element={<ScenarioPage />} />
                  <Route path="payments" element={<PaymentsLedgerPage />} />
                  <Route path="analytics" element={<AnalyticsPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Route>

                {/* Wildcard Fallback */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </CustomizationProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
