import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { applyTheme, resolvedTheme, storedTheme, systemPrefersDark } from './components/theme'

const Home = lazy(() => import('./pages/Home'))
const Architecture = lazy(() => import('./pages/Architecture'))
const Resources = lazy(() => import('./pages/Resources'))
const Dashboard = lazy(() => import('./pages/Dashboard'))

const LINKS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/architecture', label: 'Architecture' },
  { to: '/resources', label: 'Method & sources' },
  { to: '/dashboard', label: 'Results' },
]

function ThemeToggle() {
  const [theme, setTheme] = useState('light')

  useEffect(() => { setTheme(resolvedTheme()) }, [])

  // Track the system preference, but only while the visitor has made no
  // explicit choice — otherwise their choice would be overridden at sunset.
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => { if (!storedTheme()) setTheme(systemPrefersDark() ? 'dark' : 'light') }
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const toggle = useCallback(() => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    applyTheme(next)
  }, [theme])

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
    >
      {theme === 'dark' ? 'Light' : 'Dark'}
    </button>
  )
}

function Nav() {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => { setOpen(false) }, [pathname])

  return (
    <nav className="nav">
      <div className="nav-inner" style={{ position: 'relative' }}>
        <NavLink to="/" className="wordmark" aria-label="Chandralipi, home">
          <span className="latin">Chandralipi</span>
          <span className="ref">SIH26166</span>
        </NavLink>

        <div className="nav-right">
          <div className="nav-links" id="primary-nav" data-open={open}>
            {LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end} className="nav-link">
                {link.label}
              </NavLink>
            ))}
          </div>
          <ThemeToggle />
          <button
            type="button"
            className="btn nav-toggle"
            aria-expanded={open}
            aria-controls="primary-nav"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? 'Close' : 'Menu'}
          </button>
        </div>
      </div>
    </nav>
  )
}

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

function Footer() {
  return (
    <footer className="footer">
      <div className="shell" style={{ display: 'grid', gap: 10 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 18px' }}>
          <span><strong style={{ fontWeight: 600 }}>Chandralipi</strong> · “moon script”</span>
          <span>Team Severed Department · IIIT Bhubaneswar</span>
          <span>Smart India Hackathon 2026 · ISRO · SIH26166</span>
        </div>
        <span className="num" style={{ fontSize: '0.74rem', color: 'var(--ink-25)' }}>
          Lunar colour and elevation maps: NASA Scientific Visualization Studio, CGI Moon Kit
        </span>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <>
      <div className="topo" aria-hidden="true" />
      <Nav />
      <ScrollToTop />
      <main>
        <Suspense fallback={<div className="loading">loading</div>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/resources" element={<Resources />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="*" element={<Home />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </>
  )
}
