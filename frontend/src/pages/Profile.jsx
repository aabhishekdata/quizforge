import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

function StatCard({ label, value, detail }) {
  return (
    <div className="index-card p-4">
      <p className="text-xs uppercase font-num text-ink/50">{label}</p>
      <p className="font-display font-extrabold text-3xl mt-1">{value}</p>
      {detail && <p className="text-sm text-ink/60 mt-1">{detail}</p>}
    </div>
  )
}

function formatDate(value) {
  if (!value) return 'No reviews yet'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

export default function Profile() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '' })
  const [passwordMsg, setPasswordMsg] = useState('')

  useEffect(() => {
    api.get('/api/profile').then(setStats).catch(e => setError(e.message))
  }, [])

  if (error) return <p className="text-redline">{error}</p>
  if (!stats) return <p className="text-mist font-num">loading profile…</p>

  const levelPercent = Math.round(stats.level_progress * 100)
  const changePassword = async () => {
    setPasswordMsg('')
    try {
      await api.post('/api/auth/password/change', passwords)
      setPasswords({ current_password: '', new_password: '' })
      setPasswordMsg('Password updated')
    } catch (e) {
      setPasswordMsg(e.message)
    }
  }

  return (
    <div>
      <div className="flex items-end justify-between gap-4 flex-wrap mb-6">
        <div>
          <p className="text-marker font-num text-sm">{stats.is_admin ? 'Admin profile' : 'Study profile'}</p>
          <h1 className="font-display font-extrabold text-3xl">{stats.username}</h1>
        </div>
        <div className="text-right">
          <p className="font-num text-marker text-sm">Level {stats.level}</p>
          <div className="w-44 h-2 mt-2 rounded-full bg-board overflow-hidden">
            <div className="h-full bg-marker rounded-full" style={{ width: `${levelPercent}%` }} />
          </div>
          <p className="text-xs text-mist mt-1">{levelPercent}% to next level</p>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Decks studied" value={stats.decks_studied} detail={`${stats.study_sessions_completed} completed sessions`} />
        <StatCard label="Reviews" value={stats.reviews} detail={`${stats.correct_reviews} correct`} />
        <StatCard label="Accuracy" value={`${stats.accuracy}%`} detail="Across all study modes" />
        <StatCard label="Total XP" value={stats.total_xp} detail={`${stats.weekly_xp} XP this week`} />
        <StatCard label="Current streak" value={stats.streak_current} detail={`${stats.streak_longest} longest · ${stats.freeze_tokens} freezes`} />
        <StatCard label="Deck library" value={stats.decks_owned} detail={`${stats.decks_shared_with_me} shared with you`} />
        <StatCard label="Cards owned" value={stats.cards_owned} detail="Cards in your decks" />
        <StatCard label="Subjects" value={stats.subjects} detail={`${stats.achievements_earned} badges earned`} />
      </div>

      <section>
        <div className="flex items-baseline justify-between gap-3 mb-3">
          <h2 className="font-display font-bold text-xl">Recent deck activity</h2>
          <Link to="/" className="text-sm text-mist hover:text-card">All decks</Link>
        </div>
        {stats.recent_decks.length === 0 ? (
          <div className="index-card p-8 text-center">
            <p className="font-display font-bold text-lg">No study sessions yet</p>
            <p className="text-ink/60 text-sm mt-1">Study a deck and your profile will start filling in.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {stats.recent_decks.map(deck => {
              const accuracy = deck.reviews ? Math.round((deck.correct / deck.reviews) * 100) : 0
              return (
                <Link key={deck.deck_id} to={`/decks/${deck.deck_id}`} className="index-card p-4 block hover:-translate-y-0.5 transition-transform">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-display font-bold">{deck.title}</p>
                      <p className="text-sm text-ink/60 mt-1">
                        {deck.subject_name || 'Uncategorized'} · {formatDate(deck.last_studied_at)}
                      </p>
                    </div>
                    <div className="text-right font-num text-xs text-ink/50 shrink-0">
                      <p>{deck.reviews} reviews</p>
                      <p>{accuracy}% correct</p>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="font-display font-bold text-xl mb-3">Password</h2>
        <div className="index-card p-4">
          <div className="grid sm:grid-cols-2 gap-3">
            <input type="password" placeholder="Current password"
                   value={passwords.current_password}
                   onChange={e => setPasswords({ ...passwords, current_password: e.target.value })}
                   className="rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marker" />
            <input type="password" placeholder="New password"
                   value={passwords.new_password}
                   onChange={e => setPasswords({ ...passwords, new_password: e.target.value })}
                   onKeyDown={e => e.key === 'Enter' && changePassword()}
                   className="rounded-md border border-rule px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marker" />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button onClick={changePassword}
                    className="rounded-md bg-ink text-marker font-display font-bold px-4 py-2 text-sm">
              Change password
            </button>
            {passwordMsg && <p className="text-sm text-ink/60">{passwordMsg}</p>}
          </div>
        </div>
      </section>
    </div>
  )
}
