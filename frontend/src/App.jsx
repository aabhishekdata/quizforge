import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { Routes, Route, Link, NavLink, Navigate, useNavigate } from 'react-router-dom'
import { api } from './lib/api'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Upload from './pages/Upload.jsx'
import Deck from './pages/Deck.jsx'
import Study from './pages/Study.jsx'
import Leaderboard from './pages/Leaderboard.jsx'
import Achievements from './pages/Achievements.jsx'
import Admin from './pages/Admin.jsx'
import Profile from './pages/Profile.jsx'

const AuthCtx = createContext(null)
export const useAuth = () => useContext(AuthCtx)

const themes = [
  { key: 'classic', label: 'Classic' },
  { key: 'high-contrast', label: 'High contrast' },
  { key: 'color-blind', label: 'Color blind' },
  { key: 'soft-light', label: 'Soft light' },
  { key: 'spectrum', label: 'Spectrum' },
]

function XPBar({ user }) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-num text-sm text-marker">LV {user.level}</span>
      <div className="w-28 h-2 rounded-full bg-board overflow-hidden" aria-label="Level progress">
        <div className="h-full bg-marker rounded-full transition-all duration-500"
             style={{ width: `${Math.round(user.level_progress * 100)}%` }} />
      </div>
      <span className="font-num text-sm text-mist hidden sm:inline">{user.total_xp} XP</span>
      <span className="font-num text-sm" title={`${user.streak_current}-day streak`}>
        🔥 {user.streak_current}
      </span>
    </div>
  )
}

function Nav({ theme, setTheme, comicMode, setComicMode }) {
  const { user, refresh, setUser } = useAuth()
  const nav = useNavigate()
  const logout = async () => {
    await api.post('/api/auth/logout')
    setUser(null)
    nav('/login')
  }
  const link = ({ isActive }) =>
    `px-3 py-1.5 rounded-md text-sm font-medium ${isActive ? 'bg-board text-card' : 'text-mist hover:text-card'}`
  return (
    <header className="border-b border-board/80">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-4 flex-wrap">
        <Link to="/" className="brand-logo font-display font-extrabold text-xl tracking-tight">
          Quiz<span className="marker-block">Forge</span>
        </Link>
        <nav className="flex gap-1 flex-wrap">
          <NavLink to="/" end className={link}>Decks</NavLink>
          <NavLink to="/upload" className={link}>Upload</NavLink>
          <NavLink to="/leaderboard" className={link}>Leaderboard</NavLink>
          <NavLink to="/achievements" className={link}>Badges</NavLink>
          <NavLink to="/profile" className={link}>Profile</NavLink>
          {user?.is_admin && <NavLink to="/admin" className={link}>Invites</NavLink>}
        </nav>
        <div className="ml-auto flex items-center gap-3 flex-wrap justify-end">
          <label className="sr-only" htmlFor="theme-select">Theme</label>
          <select
            id="theme-select"
            value={theme}
            onChange={e => setTheme(e.target.value)}
            className="rounded-md bg-board text-card text-sm px-2 py-1.5 border border-mist/30 focus:outline-none focus:ring-2 focus:ring-marker"
            title="Theme"
          >
            {themes.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
          </select>
          <button
            type="button"
            onClick={() => setComicMode(!comicMode)}
            className={`comic-switch ${comicMode ? 'is-on' : ''}`}
            aria-pressed={comicMode}
            title="Comic mode"
          >
            <span className="comic-switch-knob" />
            <span className="comic-switch-label">Comic</span>
          </button>
          {user && <XPBar user={user} />}
          <button onClick={logout} className="text-sm text-mist hover:text-card">Sign out</button>
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = loading
  const [theme, setTheme] = useState(() => localStorage.getItem('qf_theme') || 'classic')
  const [comicMode, setComicMode] = useState(() => localStorage.getItem('qf_comic_mode') === '1')
  const refresh = useCallback(async () => {
    try { setUser(await api.get('/api/auth/me')) } catch { setUser(null) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const active = themes.some(t => t.key === theme) ? theme : 'classic'
    document.documentElement.dataset.theme = active
    localStorage.setItem('qf_theme', active)
  }, [theme])
  useEffect(() => {
    document.documentElement.dataset.layout = comicMode ? 'comic' : 'standard'
    localStorage.setItem('qf_comic_mode', comicMode ? '1' : '0')
  }, [comicMode])

  if (user === undefined) {
    return <div className="min-h-screen grid place-items-center text-mist font-num">loading…</div>
  }

  return (
    <AuthCtx.Provider value={{ user, setUser, refresh }}>
      {user ? (
        <>
          <Nav theme={theme} setTheme={setTheme} comicMode={comicMode} setComicMode={setComicMode} />
          <main className="max-w-5xl mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Upload />} />
              <Route path="/decks/:id" element={<Deck />} />
              <Route path="/decks/:id/study/:mode" element={<Study />} />
              <Route path="/leaderboard" element={<Leaderboard />} />
              <Route path="/achievements" element={<Achievements />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
        </>
      ) : (
        <Routes>
          <Route path="*" element={<Login />} />
        </Routes>
      )}
    </AuthCtx.Provider>
  )
}
