import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../App.jsx'

export default function Login() {
  const { setUser } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', password: '', invite_code: '', reset_code: '', new_password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true); setError('')
    try {
      const path = mode === 'login'
        ? '/api/auth/login'
        : mode === 'register'
          ? '/api/auth/register'
          : '/api/auth/password/reset'
      const body = mode === 'login'
        ? { username: form.username, password: form.password }
        : mode === 'register'
          ? { username: form.username, password: form.password, invite_code: form.invite_code }
          : { username: form.username, reset_code: form.reset_code, new_password: form.new_password }
      setUser(await api.post(path, body))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const field = 'w-full rounded-md bg-white border border-rule px-3 py-2 text-ink placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker'

  return (
    <div className="min-h-screen grid place-items-center px-4">
      <div className="index-card w-full max-w-sm p-8">
        <h1 className="brand-logo font-display font-extrabold text-3xl mb-1">
          Quiz<span className="marker-block">Forge</span>
        </h1>
        <p className="text-sm text-ink/60 mb-6">
          {mode === 'login'
            ? 'Welcome back. The leaderboard missed you.'
            : mode === 'register'
              ? 'Got an invite code? You\u2019re in.'
              : 'Use a reset code from an admin.'}
        </p>
        <div className="space-y-3">
          <input className={field} placeholder="Username" value={form.username}
                 onChange={e => setForm({ ...form, username: e.target.value })} />
          {mode !== 'reset' && (
            <input className={field} type="password" placeholder="Password" value={form.password}
                   onKeyDown={e => e.key === 'Enter' && submit()}
                   onChange={e => setForm({ ...form, password: e.target.value })} />
          )}
          {mode === 'register' && (
            <input className={field} placeholder="Invite code" value={form.invite_code}
                   onKeyDown={e => e.key === 'Enter' && submit()}
                   onChange={e => setForm({ ...form, invite_code: e.target.value })} />
          )}
          {mode === 'reset' && (
            <>
              <input className={field} placeholder="Reset code" value={form.reset_code}
                     onChange={e => setForm({ ...form, reset_code: e.target.value })}
                     onKeyDown={e => e.key === 'Enter' && submit()} />
              <input className={field} type="password" placeholder="New password" value={form.new_password}
                     onChange={e => setForm({ ...form, new_password: e.target.value })}
                     onKeyDown={e => e.key === 'Enter' && submit()} />
            </>
          )}
          {error && <p className="text-sm text-redline">{error}</p>}
          <button onClick={submit} disabled={busy}
                  className="w-full rounded-md bg-ink text-marker font-display font-bold py-2.5 hover:opacity-90 disabled:opacity-50">
            {busy ? '…' : mode === 'login' ? 'Sign in' : mode === 'register' ? 'Create account' : 'Reset password'}
          </button>
          <Link to="/demo"
                className="block w-full text-center rounded-md bg-board text-card font-display font-bold py-2.5 hover:ring-1 hover:ring-marker">
            Try demo deck
          </Link>
        </div>
        <div className="mt-4 flex gap-3 flex-wrap text-sm">
          <button onClick={() => { setMode(mode === 'register' ? 'login' : 'register'); setError('') }}
                  className="text-ink/60 underline underline-offset-2">
            {mode === 'register' ? 'Already registered? Sign in' : 'Have an invite code? Register'}
          </button>
          <button onClick={() => { setMode(mode === 'reset' ? 'login' : 'reset'); setError('') }}
                  className="text-ink/60 underline underline-offset-2">
            {mode === 'reset' ? 'Back to sign in' : 'Forgot password?'}
          </button>
        </div>
      </div>
    </div>
  )
}
