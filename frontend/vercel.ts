/** Build-time routing only. No payment credentials belong in this project. */
const raw = process.env.CASHFLOW_BACKEND_URL;
if (!raw) throw new Error('Set CASHFLOW_BACKEND_URL to the persistent HTTPS backend origin.');
const backend = new URL(raw);
if (backend.protocol !== 'https:' || backend.username || backend.password || backend.search || backend.hash || backend.pathname !== '/' || backend.port || !/^[a-z0-9]+(?:[.-][a-z0-9]+)+$/.test(backend.hostname) || ['localhost', '127.0.0.1', '0.0.0.0'].includes(backend.hostname)) {
  throw new Error('CASHFLOW_BACKEND_URL must be a public HTTPS origin without credentials, port or path.');
}
export const config = {
  framework: 'vite',
  installCommand: 'npm ci',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    { source: '/api/:path*', destination: `${backend.origin}/api/:path*` },
    { source: '/health', destination: `${backend.origin}/health` },
    { source: '/dashboard/:path*', destination: '/index.html' },
    ...['/login', '/signup', '/verify-email', '/forgot-password'].map(source => ({source, destination:'/index.html'})),
  ],
  headers: [{ source: '/(.*)', headers: [
    { key:'Cache-Control', value:'no-store' },
    { key:'X-Content-Type-Options', value:'nosniff' },
    { key:'Referrer-Policy', value:'no-referrer' },
    { key:'X-Frame-Options', value:'DENY' },
    { key:'Permissions-Policy', value:'camera=(), microphone=(), geolocation=()' },
    { key:'Content-Security-Policy', value:"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" },
  ]}],
};
