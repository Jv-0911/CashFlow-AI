import { useEffect, useRef, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Moon, Sun } from 'lucide-react';
import { useTheme } from '../../context';
import '../../styles/auth.css';

interface AuthLayoutProps {
  children: ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  const { theme, toggleTheme } = useTheme();
  const glowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Respect reduced motion & touch devices
    if (typeof window === 'undefined') return;
    const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isTouch = window.matchMedia('(pointer: coarse)').matches;
    if (isReduced || isTouch) return;

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight * 0.35;
    let currentX = targetX;
    let currentY = targetY;
    let frameId: number;

    const handlePointerMove = (e: PointerEvent) => {
      targetX = e.clientX;
      targetY = e.clientY;
    };

    const animate = () => {
      // Very smooth, calm interpolation with slight delay
      currentX += (targetX - currentX) * 0.05;
      currentY += (targetY - currentY) * 0.05;

      if (glowRef.current) {
        glowRef.current.style.transform = `translate3d(${currentX}px, ${currentY}px, 0) translate(-50%, -50%)`;
      }

      frameId = requestAnimationFrame(animate);
    };

    window.addEventListener('pointermove', handlePointerMove, { passive: true });
    frameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      cancelAnimationFrame(frameId);
    };
  }, []);

  return (
    <div className="auth-viewport" data-theme={theme}>
      {/* Soft restrained ambient light following cursor with slight delay */}
      <div className="auth-ambient-glow" ref={glowRef} aria-hidden="true" />

      {/* Top utility navigation */}
      <header className="auth-topbar">
        <Link to="/" className="auth-nav-back">
          <ArrowLeft size={16} />
          <span>Back to CashFlow AI</span>
        </Link>

        <button
          type="button"
          className="landing-theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </header>

      {/* Centered card container */}
      <main className="auth-card-container">
        {children}
      </main>
    </div>
  );
}
