import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const MEDALS = ['🥇', '🥈', '🥉']

export default function Leaderboard() {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get('/api/leaderboard').then(setRows) }, [])
  if (!rows) return <p className="text-mist font-num">tallying…</p>

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="font-display font-extrabold text-3xl mb-1">This week</h1>
      <p className="text-mist text-sm mb-6">XP resets every Monday. Total XP is forever.</p>
      <div className="space-y-3">
        {rows.map((r, i) => (
          <div key={r.username} className="index-card p-4 flex items-center gap-4">
            <span className="font-display font-extrabold text-xl w-8">
              {MEDALS[i] || `${i + 1}.`}
            </span>
            <div className="flex-1">
              <p className="font-semibold">{r.username}</p>
              <p className="text-xs text-ink/50 font-num">LV {r.level} · {r.total_xp} total XP · 🔥 {r.streak}</p>
            </div>
            <span className="font-num font-bold bg-marker rounded px-2 py-0.5">{r.weekly_xp} XP</span>
          </div>
        ))}
      </div>
    </div>
  )
}
