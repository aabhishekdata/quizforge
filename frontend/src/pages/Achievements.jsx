import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function Achievements() {
  const [items, setItems] = useState(null)
  useEffect(() => { api.get('/api/achievements').then(setItems) }, [])
  if (!items) return <p className="text-mist font-num">polishing badges…</p>
  const earned = items.filter(a => a.earned_at).length

  return (
    <div>
      <h1 className="font-display font-extrabold text-3xl mb-1">Badges</h1>
      <p className="text-mist text-sm mb-6 font-num">{earned} / {items.length} earned</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map(a => (
          <div key={a.key}
               className={`index-card p-4 ${a.earned_at ? '' : 'opacity-45 grayscale'}`}>
            <p className="text-2xl">{a.icon}</p>
            <p className="font-display font-bold mt-1">{a.name}</p>
            <p className="text-xs text-ink/60 mt-0.5">{a.description}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
