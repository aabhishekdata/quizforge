import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'

export default function Dashboard() {
  const [decks, setDecks] = useState(null)
  const [subjects, setSubjects] = useState([])
  const [selectedSubject, setSelectedSubject] = useState('all')
  const [subjectName, setSubjectName] = useState('')
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState('')
  const importRef = useRef()
  const loadDecks = () => api.get('/api/decks').then(setDecks).catch(() => setDecks([]))
  const loadSubjects = () => api.get('/api/subjects').then(setSubjects).catch(() => setSubjects([]))
  useEffect(() => { loadDecks(); loadSubjects() }, [])

  if (decks === null) return <p className="text-mist font-num">loading decks…</p>

  const totalDue = decks.reduce((n, d) => n + d.due_count, 0)
  const filteredDecks = decks.filter(d => {
    if (selectedSubject === 'all') return true
    if (selectedSubject === 'none') return !d.subject_id
    return String(d.subject_id) === selectedSubject
  })
  const groupedDecks = filteredDecks.reduce((groups, deck) => {
    const key = deck.subject_name || 'Uncategorized'
    groups[key] = groups[key] || []
    groups[key].push(deck)
    return groups
  }, {})

  const importDeck = async (file) => {
    if (!file) return
    setImportError('')
    setImporting(true)
    const fd = new FormData()
    fd.append('file', file)
    if (selectedSubject !== 'all' && selectedSubject !== 'none') fd.append('subject_id', selectedSubject)
    try {
      await api.upload('/api/decks/import', fd)
      await loadDecks()
    } catch (e) {
      setImportError(e.message)
    } finally {
      setImporting(false)
      if (importRef.current) importRef.current.value = ''
    }
  }
  const createSubject = async () => {
    const name = subjectName.trim()
    if (!name) return
    setImportError('')
    try {
      const subject = await api.post('/api/subjects', { name })
      setSubjectName('')
      await loadSubjects()
      setSelectedSubject(String(subject.id))
    } catch (e) {
      setImportError(e.message)
    }
  }

  return (
    <div>
      <div className="flex items-end justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="font-display font-extrabold text-3xl">Your decks</h1>
          {totalDue > 0 && (
            <p className="text-marker font-num text-sm mt-1">{totalDue} cards due for Smart Review</p>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => importRef.current.click()}
                  disabled={importing}
                  className="rounded-md bg-board text-card font-display font-bold px-4 py-2 hover:ring-1 hover:ring-marker disabled:opacity-50">
            Import deck
          </button>
          <Link to="/upload"
                className="rounded-md bg-marker text-ink font-display font-bold px-4 py-2 hover:opacity-90">
            + New deck from a file
          </Link>
        </div>
      </div>
      <input ref={importRef} type="file" accept=".json,.csv" className="hidden"
             onChange={e => importDeck(e.target.files[0])} />
      {importError && <p className="text-redline text-sm -mt-3 mb-4">{importError}</p>}

      <div className="mb-6 flex items-center gap-2 flex-wrap">
        <select value={selectedSubject} onChange={e => setSelectedSubject(e.target.value)}
                className="rounded-md bg-board px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marker">
          <option value="all">All subjects</option>
          {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          <option value="none">Uncategorized</option>
        </select>
        <input value={subjectName} onChange={e => setSubjectName(e.target.value)}
               onKeyDown={e => e.key === 'Enter' && createSubject()}
               placeholder="New subject"
               className="rounded-md bg-board px-3 py-2 text-sm placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
        <button onClick={createSubject}
                className="rounded-md bg-board px-3 py-2 text-sm font-display font-bold hover:ring-1 hover:ring-marker">
          Add subject
        </button>
      </div>

      {filteredDecks.length === 0 ? (
        <div className="index-card p-10 text-center">
          <p className="font-display font-bold text-xl mb-2">Nothing to study yet</p>
          <p className="text-ink/60 mb-4">Upload a source file, or import an existing JSON/CSV flashcard deck.</p>
          <Link to="/upload" className="inline-block rounded-md bg-ink text-marker font-display font-bold px-5 py-2.5">
            Upload your first file
          </Link>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedDecks).map(([subject, subjectDecks]) => (
            <section key={subject}>
              <div className="flex items-baseline gap-2 mb-3">
                <h2 className="font-display font-bold text-xl">{subject}</h2>
                <span className="text-xs text-mist font-num">{subjectDecks.length} decks</span>
              </div>
              <div className="grid sm:grid-cols-2 gap-5">
                {subjectDecks.map(d => (
                  <Link key={d.id} to={`/decks/${d.id}`}
                        className="index-card p-5 hover:-translate-y-0.5 transition-transform">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-display font-bold text-lg leading-tight">{d.title}</h3>
                      {d.due_count > 0 && (
                        <span className="shrink-0 font-num text-xs bg-marker text-ink rounded-full px-2 py-0.5">
                          {d.due_count} due
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-ink/60 mt-1 line-clamp-2">{d.description || '\u00A0'}</p>
                    <div className="flex gap-3 mt-3 text-xs font-num text-ink/50 flex-wrap">
                      <span>{d.card_count} cards</span>
                      {d.smart_review && <span>smart review</span>}
                      {d.is_shared_with_me && <span>shared by {d.owner_username}</span>}
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
