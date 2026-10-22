import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, AuthProvider } from './context';
import { LandingPage } from './features/landing/LandingPage';
import { AuthPlaceholder } from './features/auth/AuthPlaceholder';

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Milestone 2: Cinematic Landing Page */}
            <Route path="/" element={<LandingPage />} />

            {/* Planned Route for Milestone 3 (Auth Suite) */}
            <Route path="/login" element={<AuthPlaceholder />} />

            {/* Wildcard Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
