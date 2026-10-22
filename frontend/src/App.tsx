import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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
const DashboardPlaceholder = lazy(() =>
  import('./features/dashboard/DashboardPlaceholder').then((m) => ({ default: m.DashboardPlaceholder }))
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

              {/* Protected Dashboard Route */}
              <Route path="/dashboard" element={<DashboardPlaceholder />} />

              {/* Wildcard Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
