import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { isUploadUnlocked, unlockUpload, UPLOAD_UNLOCK_CODE } from '../lib/uploadGate'

export default function Upload() {
  const nav = useNavigate()
  const inputRef = useRef()
  const [unlocked, setUnlocked] = useState(() => isUploadUnlocked())
  const [code, setCode] = useState('')
  const [doc, setDoc] = useState(null)
  const [subjects, setSubjects] = useState([])
  const [subjectId, setSubjectId] = useState('')
  const [newSubject, setNewSubject] = useState('')
  const [hq, setHq] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  const tryUnlock = () => {
    if (code.trim() === UPLOAD_UNLOCK_CODE) {
      unlockUpload()
      setUnlocked(true)
      setError('')
    } else {
      setError('Incorrect upload code')
    }
  }

  const send = async (file) => {
    setError('')
    const fd = new FormData()
    fd.append('file', file)
    fd.append('high_quality', hq)
    fd.append('upload_code', UPLOAD_UNLOCK_CODE)
    try {
      let chosenSubjectId = subjectId
      if (newSubject.trim()) {
        const subject = await api.post('/api/subjects', { name: newSubject.trim() })
        chosenSubjectId = String(subject.id)
        setSubjectId(chosenSubjectId)
        setNewSubject('')
        setSubjects(await api.get('/api/subjects'))
      }
      if (chosenSubjectId) fd.append('subject_id', chosenSubjectId)
      setDoc(await api.upload('/api/documents', fd))
    }
    catch (e) { setError(e.message) }
  }

  useEffect(() => {
    api.get('/api/subjects').then(setSubjects).catch(() => setSubjects([]))
  }, [])

  // poll status while generating
  useEffect(() => {
    if (!doc || doc.status === 'ready' || doc.status === 'failed') return
    const t = setInterval(async () => {
      try { setDoc(await api.get(`/api/documents/${doc.id}`)) } catch {}
    }, 2000)
    return () => clearInterval(t)
  }, [doc])

  useEffect(() => {
    if (doc?.status === 'ready') {
      const t = setTimeout(() => nav('/'), 1200)
      return () => clearTimeout(t)
    }
  }, [doc, nav])

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="font-display font-extrabold text-3xl mb-6">New deck from a file</h1>

      {!unlocked && (
        <div className="index-card p-8">
          <p className="font-display font-bold text-xl">Upload is locked</p>
          <p className="text-ink/60 text-sm mt-2">
            Enter the upload access code to create decks from files.
          </p>
          <div className="mt-5 flex gap-2 flex-col sm:flex-row">
            <input
              value={code}
              onChange={e => setCode(e.target.value)}
              onKeyDown={e => {
                if (e.key !== 'Enter') return
                tryUnlock()
              }}
              placeholder="Upload code"
              className="flex-1 rounded-md border border-rule px-3 py-2 text-ink placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker"
            />
            <button
              onClick={tryUnlock}
              className="rounded-md bg-ink px-4 py-2 font-display font-bold text-marker"
            >
              Unlock
            </button>
          </div>
          {error && <p className="text-redline text-sm mt-3">{error}</p>}
        </div>
      )}

      {unlocked && !doc && (
        <>
          <div className="mb-4 flex items-center gap-2 flex-wrap">
            <select value={subjectId} onChange={e => setSubjectId(e.target.value)}
                    className="rounded-md bg-board px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marker">
              <option value="">Uncategorized</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input value={newSubject} onChange={e => setNewSubject(e.target.value)}
                   placeholder="New subject"
                   className="rounded-md bg-board px-3 py-2 text-sm placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
          </div>
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); e.dataTransfer.files[0] && send(e.dataTransfer.files[0]) }}
            onClick={() => inputRef.current.click()}
            role="button" tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && inputRef.current.click()}
            className={`index-card p-10 text-center cursor-pointer transition-transform ${dragging ? 'scale-[1.02]' : ''}`}
          >
            <p className="font-display font-bold text-xl">Drop a file here</p>
            <p className="text-ink/60 text-sm mt-1">PDF / DOCX / PPTX / EPUB / Markdown - up to 25MB</p>
            <p className="text-ink/40 text-xs mt-4">or click to browse</p>
            <input ref={inputRef} type="file" accept=".pdf,.docx,.pptx,.epub,.md" className="hidden"
                   onChange={e => e.target.files[0] && send(e.target.files[0])} />
          </div>
          <label className="flex items-center gap-2 mt-4 text-sm text-mist cursor-pointer">
            <input type="checkbox" checked={hq} onChange={e => setHq(e.target.checked)}
                   className="accent-marker" />
            High-quality generation (slower, costs a bit more)
          </label>
          {error && <p className="text-redline text-sm mt-3">{error}</p>}
        </>
      )}

      {unlocked && doc && (
        <div className="index-card p-8">
          <p className="font-display font-bold text-lg">{doc.filename}</p>
          {doc.status === 'failed' ? (
            <>
              <p className="text-redline text-sm mt-2">{doc.error}</p>
              <button onClick={() => setDoc(null)} className="mt-4 text-sm underline underline-offset-2">
                Try another file
              </button>
            </>
          ) : doc.status === 'ready' ? (
            <p className="text-ink mt-2">✅ {doc.progress} — taking you to your decks…</p>
          ) : (
            <div className="mt-3">
              <p className="text-ink/70 text-sm">{doc.progress}</p>
              <div className="h-1.5 mt-3 rounded-full bg-rule overflow-hidden">
                <div className="h-full w-1/3 bg-marker rounded-full animate-pulse" />
              </div>
              <p className="text-ink/40 text-xs mt-3">
                +15 XP for feeding the machine. You can leave this page — the deck will appear when it's done.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
