import { useState, useEffect, useRef } from 'react';
import { Link, NavLink, Outlet, Navigate, useNavigate, useLocation } from 'react-router-dom';
import {
  BarChart3,
  Bell,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Gauge,
  GitBranch,
  LogOut,
  Moon,
  PanelLeft,
  Search,
  Settings,
  Sparkles,
  Sun,
  TrendingUp,
} from 'lucide-react';
import { useAuth, useTheme } from '../../context';
import '../../styles/dashboard.css';

export function DashboardLayout() {
  const { user, isAuthenticated, logout, loading } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [notifDropdownOpen, setNotifDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const userMenuRef = useRef<HTMLDivElement>(null);
  const notifMenuRef = useRef<HTMLDivElement>(null);

  // Close menus on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserDropdownOpen(false);
      }
      if (notifMenuRef.current && !notifMenuRef.current.contains(e.target as Node)) {
        setNotifDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Route protection
  if (loading) return <div role="status">Loading workspace…</div>;
  if (!isAuthenticated || !user) return <Navigate to="/login" replace />;

  const handleSignOut = async () => {
    try {await logout();navigate('/login');} catch {window.alert('Sign out could not be confirmed. Please retry.');}
  };

  // Determine current page title from pathname
  const getPageTitle = () => {
    const path = location.pathname;
    if (path.includes('/forecast')) return 'Forecast Engine';
    if (path.includes('/rescue')) return 'AI Rescue Suite';
    if (path.includes('/scenarios')) return 'Scenario Simulation';
    if (path.includes('/payments')) return 'Payments & Ledger';
    if (path.includes('/analytics')) return 'Analytics';
    if (path.includes('/settings')) return 'Settings';
    return 'Overview';
  };

  const userInitials = user.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="dashboard-root" data-theme={theme}>
      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`dashboard-sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${
          mobileMenuOpen ? 'mobile-open' : ''
        }`}
      >
        {/* Sidebar Brand Header */}
        <div className="sidebar-header">
          <Link to="/dashboard" className="sidebar-brand">
            <div className="sidebar-brand-icon">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" stroke="#7896B0" />
              </svg>
            </div>
            <div className="sidebar-brand-info">
              <span className="sidebar-brand-name">CashFlow AI</span>
              <span className="sidebar-brand-sub">Intelligent Finance</span>
            </div>
          </Link>

          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* Navigation Sections (AdminCN layout) */}
        <nav
          className="sidebar-nav"
          onClick={(e) => {
            if ((e.target as HTMLElement).closest('a')) {
              setMobileMenuOpen(false);
            }
          }}
        >
          {/* Section 1: Core Intelligence */}
          <div className="sidebar-section">
            <span className="sidebar-section-title">Core Intelligence</span>

            <NavLink
              to="/dashboard"
              end
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Gauge size={18} className="sidebar-link-icon" />
              <span>Overview</span>
            </NavLink>

            <NavLink
              to="/dashboard/forecast"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <TrendingUp size={18} className="sidebar-link-icon" />
              <span>Forecast</span>
            </NavLink>

            <NavLink
              to="/dashboard/rescue"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Sparkles size={18} className="sidebar-link-icon" />
              <span>AI Rescue</span>
              <span className="sidebar-link-badge">M6</span>
            </NavLink>

            <NavLink
              to="/dashboard/scenarios"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <GitBranch size={18} className="sidebar-link-icon" />
              <span>Scenarios</span>
              <span className="sidebar-link-badge">M7</span>
            </NavLink>
          </div>

          {/* Section 2: Transactions & Ledger */}
          <div className="sidebar-section">
            <span className="sidebar-section-title">Transactions & Ledger</span>

            <NavLink
              to="/dashboard/payments"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <CreditCard size={18} className="sidebar-link-icon" />
              <span>Payments & Ledger</span>
              <span className="sidebar-link-badge">M8</span>
            </NavLink>

            <NavLink
              to="/dashboard/analytics"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <BarChart3 size={18} className="sidebar-link-icon" />
              <span>Analytics</span>
            </NavLink>
          </div>

          {/* Section 3: Preferences */}
          <div className="sidebar-section">
            <span className="sidebar-section-title">Preferences</span>

            <NavLink
              to="/dashboard/settings"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Settings size={18} className="sidebar-link-icon" />
              <span>Settings</span>
            </NavLink>
          </div>
        </nav>

        {/* Sidebar Footer User Card */}
        <div className="sidebar-footer">
          <div className="sidebar-user-pill">
            <div className="sidebar-user-avatar">{userInitials}</div>
            <div className="sidebar-user-text">
              <span className="sidebar-user-name">{user.name}</span>
              <span className="sidebar-user-role">{user.businessName || 'CashFlow Studio'}</span>
            </div>
          </div>

          <button
            type="button"
            className="sidebar-logout-btn"
            onClick={handleSignOut}
            aria-label="Sign Out"
            title="Sign Out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main Container */}
      <div className="dashboard-main">
        {/* Top Toolbar (AdminCN header) */}
        <header className="dashboard-toolbar">
          <div className="toolbar-left">
            <button
              type="button"
              className="toolbar-menu-btn"
              onClick={() => {
                if (window.innerWidth <= 900) {
                  setMobileMenuOpen(!mobileMenuOpen);
                } else {
                  setSidebarCollapsed(!sidebarCollapsed);
                }
              }}
              aria-label="Toggle Navigation Menu"
            >
              <PanelLeft size={18} />
            </button>

            <div className="toolbar-breadcrumb">
              <span>Dashboard</span>
              <span style={{ color: '#666A91' }}>/</span>
              <span className="toolbar-breadcrumb-title">{getPageTitle()}</span>
            </div>
          </div>

          {/* Search Box with ⌘K badge */}
          <div className="toolbar-search">
            <Search size={15} className="toolbar-search-icon" />
            <input
              type="text"
              className="toolbar-search-input"
              placeholder="Type to search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search dashboard"
            />
            <kbd className="toolbar-search-kbd">⌘K</kbd>
          </div>

          {/* Right Toolbar Actions */}
          <div className="toolbar-right">
            {/* API Status Pill */}
            <div className="toolbar-api-status" title="Fictional single-business demonstration">
              <span className="api-status-dot" />
              <span>Demo Workspace</span>
            </div>

            {/* Notifications Popover Menu */}
            <div className="toolbar-user-menu" ref={notifMenuRef}>
              <button
                type="button"
                className="toolbar-action-btn"
                onClick={() => setNotifDropdownOpen(!notifDropdownOpen)}
                aria-label="Notifications"
                title="Notifications"
              >
                <Bell size={18} />
                <span className="notif-badge-dot" />
              </button>

              {notifDropdownOpen && (
                <div className="notif-dropdown-popover">
                  <div className="notif-header">
                    <span>Notifications</span>
                    <span style={{ fontSize: 10, color: '#7896B0' }}>2 Unread</span>
                  </div>

                  <div className="notif-item">
                    <Sparkles size={16} color="#fbbf24" style={{ flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <div className="notif-item-title">Safety Reserve Notice</div>
                      <div className="notif-item-desc">
                        Projected cash buffer requires $500.00 recovery by Oct 14.
                      </div>
                    </div>
                  </div>

                  <div className="notif-item">
                    <CreditCard size={16} color="#34d399" style={{ flexShrink: 0, marginTop: 2 }} />
                    <div>
                      <div className="notif-item-title">Sandbox Ledger Item</div>
                      <div className="notif-item-desc">
                        Invoice #INV-2041 ready for simulated PayPal follow-up.
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Theme Toggle */}
            <button
              type="button"
              className="toolbar-action-btn"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>

            {/* User Avatar Menu Dropdown */}
            <div className="toolbar-user-menu" ref={userMenuRef}>
              <button
                type="button"
                className="toolbar-user-btn"
                onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                aria-label="User Account Menu"
              >
                <div className="toolbar-avatar">{userInitials}</div>
                <span className="toolbar-avatar-dot" />
              </button>

              {userDropdownOpen && (
                <div className="user-dropdown-popover">
                  <div className="dropdown-user-header">
                    <span className="dropdown-user-name">{user.name}</span>
                    <span className="dropdown-user-email">{user.email}</span>
                    <span style={{ fontSize: 10, color: '#7896B0', marginTop: 2 }}>
                      {user.businessName || 'CashFlow Studio'}
                    </span>
                  </div>

                  <span className="demo-banner-tag" style={{ textAlign: 'center' }}>
                    Demo Mode Active
                  </span>

                  <Link to="/" className="dropdown-item">
                    <span>Return to Landing Page</span>
                  </Link>

                  <Link to="/dashboard/settings" className="dropdown-item">
                    <Settings size={14} />
                    <span>Account Settings</span>
                  </Link>

                  <button
                    type="button"
                    className="dropdown-item danger"
                    onClick={handleSignOut}
                  >
                    <LogOut size={14} />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Dashboard Dynamic Content */}
        <Outlet />
      </div>
    </div>
  );
}
