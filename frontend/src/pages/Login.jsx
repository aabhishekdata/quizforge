import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../App.jsx'

export default function Login() {
  const { setUser } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', password: '', invite_code: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true); setError('')
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const body = mode === 'login'
        ? { username: form.username, password: form.password }
        : form
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
        <h1 className="font-display font-extrabold text-3xl mb-1">
          Quiz<span className="marker-underline px-0.5">Forge</span>
        </h1>
        <p className="text-sm text-ink/60 mb-6">
          {mode === 'login' ? 'Welcome back. The leaderboard missed you.' : 'Got an invite code? You\u2019re in.'}
        </p>
        <div className="space-y-3">
          <input className={field} placeholder="Username" value={form.username}
                 onChange={e => setForm({ ...form, username: e.target.value })} />
          <input className={field} type="password" placeholder="Password" value={form.password}
                 onKeyDown={e => e.key === 'Enter' && submit()}
                 onChange={e => setForm({ ...form, password: e.target.value })} />
          {mode === 'register' && (
            <input className={field} placeholder="Invite code" value={form.invite_code}
                   onKeyDown={e => e.key === 'Enter' && submit()}
                   onChange={e => setForm({ ...form, invite_code: e.target.value })} />
          )}
          {error && <p className="text-sm text-redline">{error}</p>}
          <button onClick={submit} disabled={busy}
                  className="w-full rounded-md bg-ink text-marker font-display font-bold py-2.5 hover:opacity-90 disabled:opacity-50">
            {busy ? '…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </div>
        <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
                className="mt-4 text-sm text-ink/60 underline underline-offset-2">
          {mode === 'login' ? 'Have an invite code? Register' : 'Already registered? Sign in'}
        </button>
      </div>
    </div>
  )
}
