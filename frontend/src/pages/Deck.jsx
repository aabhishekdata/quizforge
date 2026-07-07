import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../App.jsx'

export default function Deck({ demo = false }) {
  const { id } = useParams()
  const nav = useNavigate()
  const { user } = useAuth()
  const [deck, setDeck] = useState(null)
  const [cards, setCards] = useState([])
  const [editing, setEditing] = useState(null) // card id
  const [draft, setDraft] = useState({ front: '', back: '' })
  const [shareName, setShareName] = useState('')
  const [groups, setGroups] = useState([])
  const [subjects, setSubjects] = useState([])
  const [newSubject, setNewSubject] = useState('')
  const [shareGroupId, setShareGroupId] = useState('')
  const [msg, setMsg] = useState('')

  const load = () => {
    const deckId = demo ? 'mental-models' : id
    const base = demo ? '/api/demo/decks' : '/api/decks'
    api.get(`${base}/${deckId}`).then(setDeck).catch(() => nav(demo ? '/login' : '/'))
    api.get(`${base}/${deckId}/cards`).then(setCards)
  }
  useEffect(load, [id, demo])
  useEffect(() => {
    if (!demo && user?.is_admin) api.get('/api/admin/groups').then(setGroups).catch(() => setGroups([]))
  }, [user?.is_admin, demo])
  useEffect(() => {
    if (!demo) api.get('/api/subjects').then(setSubjects).catch(() => setSubjects([]))
  }, [demo])

  if (!deck) return <p className="text-mist font-num">loading…</p>
  const mine = !demo && user && deck.owner_id === user.id
  const mcqCount = cards.filter(c => c.mcq_options).length

  const modes = [
    { key: 'flashcard', name: 'Flashcards', desc: 'Flip and self-grade', enabled: cards.length > 0 },
    { key: 'mcq', name: 'Multiple choice', desc: 'Timed bonus XP', enabled: mcqCount > 0 },
    { key: 'type', name: 'Type answer', desc: 'Fuzzy matching', enabled: cards.length > 0 },
    { key: 'match', name: 'Match', desc: 'Pair grid, race the clock', enabled: cards.length >= 4 },
  ]

  const saveCard = async (cardId) => {
    const updated = await api.patch(`/api/decks/${id}/cards/${cardId}`, draft)
    setCards(cards.map(c => (c.id === cardId ? updated : c)))
    setEditing(null)
  }
  const deleteCard = async (cardId) => {
    await api.del(`/api/decks/${id}/cards/${cardId}`)
    setCards(cards.filter(c => c.id !== cardId))
  }
  const toggleSmart = async () => {
    const updated = await api.patch(`/api/decks/${id}`, { smart_review: !deck.smart_review })
    setDeck(updated)
  }
  const moveSubject = async (subjectId) => {
    const updated = await api.patch(`/api/decks/${id}`, { subject_id: subjectId ? Number(subjectId) : null })
    setDeck(updated)
  }
  const createAndMoveSubject = async () => {
    const name = newSubject.trim()
    if (!name) return
    setMsg('')
    try {
      const subject = await api.post('/api/subjects', { name })
      setSubjects([...subjects, subject].sort((a, b) => a.name.localeCompare(b.name)))
      setNewSubject('')
      const updated = await api.patch(`/api/decks/${id}`, { subject_id: subject.id })
      setDeck(updated)
    } catch (e) { setMsg(e.message) }
  }
  const share = async () => {
    setMsg('')
    try {
      await api.post(`/api/decks/${id}/share`, { username: shareName.trim() })
      setMsg(`Shared with ${shareName.trim()}`)
      setShareName('')
    } catch (e) { setMsg(e.message) }
  }
  const shareGroup = async () => {
    if (!shareGroupId) return
    setMsg('')
    try {
      const group = groups.find(g => String(g.id) === String(shareGroupId))
      await api.post(`/api/decks/${id}/share-group`, { group_id: Number(shareGroupId) })
      setMsg(`Shared with ${group?.name || 'group'}`)
      setShareGroupId('')
    } catch (e) { setMsg(e.message) }
  }
  const exportDeck = async (format) => {
    setMsg('')
    try {
      await api.download(`/api/decks/${id}/export.${format}`)
    } catch (e) { setMsg(e.message) }
  }

  return (
    <div>
      <Link to={demo ? "/login" : "/"} className="text-sm text-mist hover:text-card">
        {demo ? '← Sign in' : '← All decks'}
      </Link>
      <div className="flex items-start justify-between gap-4 mt-2 mb-6 flex-wrap">
        <div>
          <h1 className="font-display font-extrabold text-3xl">{deck.title}</h1>
          <p className="text-mist text-sm mt-1">{deck.card_count} cards
            {deck.subject_name && ` · ${deck.subject_name}`}
            {deck.is_shared_with_me && ` · shared by ${deck.owner_username}`}</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap justify-end">
          {mine && (
            <div className="flex items-center gap-2 flex-wrap justify-end">
              <select value={deck.subject_id || ''} onChange={e => moveSubject(e.target.value)}
                      className="rounded-md bg-board px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-marker">
                <option value="">Uncategorized</option>
                {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <input value={newSubject} onChange={e => setNewSubject(e.target.value)}
                     onKeyDown={e => e.key === 'Enter' && createAndMoveSubject()}
                     placeholder="New subject"
                     className="w-32 rounded-md bg-board px-3 py-1.5 text-sm placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
              <button onClick={createAndMoveSubject}
                      className="text-sm rounded-md bg-board px-3 py-1.5 hover:ring-1 hover:ring-marker">
                Add
              </button>
            </div>
          )}
          {!demo && (
            <>
              <button onClick={() => exportDeck('json')}
                      className="text-sm rounded-md bg-board px-3 py-1.5 hover:ring-1 hover:ring-marker">
                Export JSON
              </button>
              <button onClick={() => exportDeck('csv')}
                      className="text-sm rounded-md bg-board px-3 py-1.5 hover:ring-1 hover:ring-marker">
                Export CSV
              </button>
            </>
          )}
          {mine && (
            <label className="flex items-center gap-2 text-sm text-mist cursor-pointer">
              <input type="checkbox" checked={deck.smart_review} onChange={toggleSmart} className="accent-marker" />
              Smart Review (spaced repetition)
            </label>
          )}
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {modes.map(m => (
          <button key={m.key} disabled={!m.enabled}
                  onClick={() => nav(demo ? `/demo/study/${m.key}` : `/decks/${id}/study/${m.key}`)}
                  className="text-left rounded-lg bg-board p-4 hover:ring-2 hover:ring-marker disabled:opacity-40 disabled:hover:ring-0">
            <p className="font-display font-bold">{m.name}</p>
            <p className="text-xs text-mist mt-0.5">{m.desc}</p>
          </button>
        ))}
      </div>

      {deck.smart_review && deck.due_count > 0 && (
        <button onClick={() => nav(`/decks/${id}/study/flashcard?smart=1`)}
                className="mb-8 rounded-md bg-marker text-ink font-display font-bold px-4 py-2">
          🧠 Review {deck.due_count} due cards
        </button>
      )}

      {!demo && user?.is_admin && (
        <div className="mb-8 rounded-lg border border-board/70 p-4">
          <p className="font-display font-bold mb-3">Admin sharing</p>
          <div className="flex items-center gap-2 flex-wrap">
            <input value={shareName} onChange={e => setShareName(e.target.value)}
                   placeholder="Username"
                   className="rounded-md bg-board px-3 py-1.5 text-sm placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
            <button onClick={share} className="text-sm rounded-md bg-board px-3 py-1.5 hover:ring-1 hover:ring-marker">
              Share to user
            </button>
            <select value={shareGroupId} onChange={e => setShareGroupId(e.target.value)}
                    className="rounded-md bg-board px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-marker">
              <option value="">Select group</option>
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
            <button onClick={shareGroup} disabled={!shareGroupId}
                    className="text-sm rounded-md bg-board px-3 py-1.5 hover:ring-1 hover:ring-marker disabled:opacity-40">
              Share to group
            </button>
          </div>
          {msg && <p className="text-sm text-mist mt-2">{msg}</p>}
        </div>
      )}

      <h2 className="font-display font-bold text-xl mb-3">Cards</h2>
      <div className="space-y-3">
        {cards.map(c => (
          <div key={c.id} className="index-card p-4 text-sm">
            {editing === c.id ? (
              <div className="space-y-2">
                <textarea className="w-full rounded border border-rule p-2" rows={2}
                          value={draft.front} onChange={e => setDraft({ ...draft, front: e.target.value })} />
                <textarea className="w-full rounded border border-rule p-2" rows={2}
                          value={draft.back} onChange={e => setDraft({ ...draft, back: e.target.value })} />
                <div className="flex gap-2">
                  <button onClick={() => saveCard(c.id)} className="rounded bg-ink text-marker px-3 py-1 font-bold">Save</button>
                  <button onClick={() => setEditing(null)} className="text-ink/60 underline">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between gap-4">
                <div>
                  <p className="font-semibold">{c.front}</p>
                  <p className="text-ink/60 mt-1">{c.back}</p>
                  {c.learning_meta?.elaboration && (
                    <p className="text-ink/60 mt-2 text-xs leading-relaxed">{c.learning_meta.elaboration}</p>
                  )}
                  {c.learning_meta?.real_world_example && (
                    <p className="text-ink/50 mt-1 text-xs leading-relaxed">
                      Example: {c.learning_meta.real_world_example}
                    </p>
                  )}
                  <p className="text-ink/40 text-xs mt-1 font-num">
                    {c.card_type || 'recall'} · {c.difficulty}{c.source_ref ? ` · ${c.source_ref}` : ''}{c.mcq_options ? ' · MCQ' : ''}
                  </p>
                </div>
                {mine && (
                  <div className="shrink-0 flex gap-3 text-xs">
                    <button className="underline"
                            onClick={() => { setEditing(c.id); setDraft({ front: c.front, back: c.back }) }}>
                      Edit
                    </button>
                    <button className="text-redline underline" onClick={() => deleteCard(c.id)}>Delete</button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
