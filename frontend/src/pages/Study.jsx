import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../App.jsx'

function levenshteinOk(a, b) {
  a = a.trim().toLowerCase(); b = b.trim().toLowerCase()
  if (!a || !b) return false
  if (a === b) return true
  const m = a.length, n = b.length
  if (Math.abs(m - n) > 3) return false
  const dp = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)])
  for (let j = 0; j <= n; j++) dp[0][j] = j
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
  const dist = dp[m][n]
  return dist <= Math.max(1, Math.floor(b.length * 0.2))
}

function XPFloat({ bursts }) {
  return (
    <div className="pointer-events-none fixed inset-x-0 top-24 flex justify-center z-50">
      {bursts.map(b => (
        <span key={b.id} className="absolute font-num font-bold text-marker animate-floatxp">
          +{b.amount} XP
        </span>
      ))}
    </div>
  )
}

export default function Study({ demo = false }) {
  const { id, mode } = useParams()
  const [params] = useSearchParams()
  const smart = params.get('smart') === '1'
  const { refresh } = useAuth()

  const [cards, setCards] = useState(null)
  const [idx, setIdx] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [combo, setCombo] = useState(0)
  const [correctCount, setCorrectCount] = useState(0)
  const [bursts, setBursts] = useState([])
  const [achToast, setAchToast] = useState(null)
  const [done, setDone] = useState(null)
  const [error, setError] = useState('')
  const startRef = useRef(Date.now())

  // per-mode state
  const [picked, setPicked] = useState(null)       // mcq
  const [typed, setTyped] = useState('')           // type
  const [typeResult, setTypeResult] = useState(null)
  const [matchState, setMatchState] = useState(null) // match

  useEffect(() => {
    const deckId = demo ? 'mental-models' : id
    const path = demo
      ? `/api/demo/study/${deckId}/session?mode=${mode === 'match' ? 'flashcard' : mode}&limit=${mode === 'match' ? 6 : 20}`
      : `/api/study/${deckId}/session?mode=${mode === 'match' ? 'flashcard' : mode}&limit=${mode === 'match' ? 6 : 20}&smart=${smart}`
    api.get(path)
      .then(cs => {
        setCards(cs)
        startRef.current = Date.now()
        if (mode === 'match') {
          const tiles = cs.flatMap(c => [
            { key: `f${c.id}`, cardId: c.id, text: c.front },
            { key: `b${c.id}`, cardId: c.id, text: c.back.slice(0, 90) },
          ]).sort(() => Math.random() - 0.5)
          setMatchState({ tiles, selected: null, matched: new Set(), wrongPair: null })
        }
      })
      .catch(e => setError(e.message))
  }, [id, mode, smart, demo])

  const card = cards?.[idx]

  const pushBurst = (amount) => {
    const b = { id: Date.now() + Math.random(), amount }
    setBursts(x => [...x, b])
    setTimeout(() => setBursts(x => x.filter(y => y.id !== b.id)), 900)
  }

  const sendReview = async (rating, correct, msTaken = null, cardId = null) => {
    if (!demo) {
      try {
        const res = await api.post('/api/study/review', {
          card_id: cardId ?? card?.id,
          mode, rating, correct, ms_taken: msTaken, combo,
        })
        pushBurst(res.xp_awarded)
        if (res.new_achievements.length) {
          setAchToast(res.new_achievements[0])
          setTimeout(() => setAchToast(null), 3000)
        }
        refresh()
      } catch {}
    }
    setCombo(correct ? combo + 1 : 0)
    if (correct) setCorrectCount(c => c + 1)
  }

  const advance = () => {
    setRevealed(false); setPicked(null); setTyped(''); setTypeResult(null)
    if (idx + 1 >= cards.length) finish()
    else setIdx(idx + 1)
  }

  const finish = async () => {
    if (demo) {
      setDone({ xp_awarded: 0, new_achievements: [] })
      return
    }
    try {
      const res = await api.post('/api/study/session/complete', {
        deck_id: Number(id), cards_seen: cards.length, correct: correctCount,
      })
      setDone(res)
      refresh()
    } catch { setDone({ xp_awarded: 0 }) }
  }

  if (error) return (
    <div className="text-center py-16">
      <p className="text-mist">{error}</p>
      <Link to={demo ? "/demo" : `/decks/${id}`} className="underline text-sm mt-2 inline-block">Back to deck</Link>
    </div>
  )
  if (!cards) return <p className="text-mist font-num">shuffling cards…</p>

  if (done) return (
    <div className="max-w-md mx-auto index-card p-8 text-center animate-pop">
      <p className="font-display font-extrabold text-2xl">Session complete</p>
      <p className="font-num text-lg mt-2">{correctCount}/{cards.length} correct</p>
      <p className="text-marker font-num mt-1 bg-ink inline-block rounded px-2 py-0.5">
        +{done.xp_awarded} XP finish bonus
      </p>
      {done.new_achievements?.map(a => (
        <p key={a.key} className="mt-2 text-sm">{a.icon} Unlocked: <b>{a.name}</b> (+{a.xp} XP)</p>
      ))}
      <div className="mt-6 flex justify-center gap-3">
        <Link to={demo ? "/demo" : `/decks/${id}`} className="rounded-md bg-ink text-marker font-display font-bold px-4 py-2">
          Back to deck
        </Link>
      </div>
    </div>
  )

  const progress = `${idx + 1} / ${cards.length}`

  // ---------- MATCH MODE ----------
  if (mode === 'match' && matchState) {
    const { tiles, selected, matched, wrongPair } = matchState
    const clickTile = (t) => {
      if (matched.has(t.key) || wrongPair) return
      if (!selected) return setMatchState({ ...matchState, selected: t })
      if (selected.key === t.key) return setMatchState({ ...matchState, selected: null })
      if (selected.cardId === t.cardId) {
        const m = new Set(matched); m.add(t.key); m.add(selected.key)
        setMatchState({ ...matchState, matched: m, selected: null })
        sendReview(3, true, Date.now() - startRef.current, t.cardId)
        if (m.size === tiles.length) setTimeout(finish, 600)
      } else {
        setMatchState({ ...matchState, wrongPair: [selected.key, t.key], selected: null })
        sendReview(1, false, null, t.cardId)
        setTimeout(() => setMatchState(s => ({ ...s, wrongPair: null })), 500)
      }
    }
    return (
      <div>
        <XPFloat bursts={bursts} />
        <Header combo={combo} progress={`${matched.size / 2} / ${tiles.length / 2} pairs`} deckId={id} demo={demo} />
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-6">
          {tiles.map(t => {
            const isSel = selected?.key === t.key
            const isWrong = wrongPair?.includes(t.key)
            const isMatched = matched.has(t.key)
            return (
              <button key={t.key} onClick={() => clickTile(t)}
                      className={`index-card p-3 pt-3 text-sm text-left min-h-24 transition-all
                        ${isMatched ? 'opacity-25 scale-95' : ''}
                        ${isSel ? 'ring-4 ring-marker' : ''}
                        ${isWrong ? 'ring-4 ring-redline' : ''}`}>
                {t.text}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // ---------- CARD MODES ----------
  return (
    <div className="max-w-4xl mx-auto">
      <XPFloat bursts={bursts} />
      {achToast && (
        <div className="fixed top-4 inset-x-0 flex justify-center z-50">
          <div className="animate-pop rounded-md bg-marker text-ink font-display font-bold px-4 py-2 shadow-lg">
            {achToast.icon} {achToast.name} unlocked! +{achToast.xp} XP
          </div>
        </div>
      )}
      <Header combo={combo} progress={progress} deckId={id} demo={demo} />

      {mode === 'flashcard' && (
        <div className="mt-6">
          <div className="index-card flex max-h-[calc(100vh-11rem)] min-h-[min(34rem,calc(100vh-11rem))] flex-col overflow-hidden">
            <div className="shrink-0 border-b border-rule p-4 sm:p-6">
              <div className="flex flex-wrap items-center gap-2 mb-4 text-xs font-num text-ink/50">
              <span>{card.card_type || 'recall'}</span>
              <span>{card.difficulty}</span>
              {card.source_ref && <span>{card.source_ref}</span>}
              </div>

              <section>
                <p className="text-xs uppercase font-num text-ink/50 mb-2">Question</p>
                <h1 className="font-display font-extrabold text-xl sm:text-2xl leading-tight">
                  {card.front}
                </h1>
              </section>
            </div>

            {!revealed ? (
              <div className="grid flex-1 place-items-center p-4 sm:p-8">
                <button
                  onClick={() => setRevealed(true)}
                  className="w-full sm:w-auto rounded-md bg-ink text-marker font-display font-bold px-6 py-3 hover:opacity-90"
                >
                  Reveal answer
                </button>
              </div>
            ) : (
              <>
                <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6 animate-pop">
                  <div>
                  <p className="text-xs uppercase font-num text-ink/50 mb-2">Answer</p>
                    <p className="text-base sm:text-lg leading-relaxed">{card.back}</p>
                  </div>

                {(card.learning_meta?.elaboration || card.learning_meta?.real_world_example || card.learning_meta?.misconception_note) && (
                    <div className="grid gap-4 mt-5 lg:grid-cols-2">
                    {card.learning_meta?.elaboration && (
                      <section className="rounded-md bg-board/10 border border-rule p-4">
                        <p className="text-xs uppercase font-num text-ink/50 mb-2">Why it matters</p>
                        <p className="text-sm leading-relaxed text-ink/70">{card.learning_meta.elaboration}</p>
                      </section>
                    )}
                    {card.learning_meta?.real_world_example && (
                      <section className="rounded-md bg-board/10 border border-rule p-4">
                        <p className="text-xs uppercase font-num text-ink/50 mb-2">Example</p>
                        <p className="text-sm leading-relaxed text-ink/70">{card.learning_meta.real_world_example}</p>
                      </section>
                    )}
                    {card.learning_meta?.misconception_note && (
                      <section className="rounded-md bg-board/10 border border-rule p-4 sm:col-span-2">
                        <p className="text-xs uppercase font-num text-ink/50 mb-2">Common trap</p>
                        <p className="text-sm leading-relaxed text-ink/70">{card.learning_meta.misconception_note}</p>
                      </section>
                    )}
                  </div>
                )}
                </div>

                <div className="shrink-0 border-t border-rule bg-card/95 p-3 sm:p-4">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[['Again', 1, false], ['Hard', 2, true], ['Good', 3, true], ['Easy', 4, true]].map(([label, r, ok]) => (
                    <button key={label}
                            onClick={async () => { await sendReview(r, ok); advance() }}
                            className={`rounded-md py-3 font-display font-bold
                              ${r === 1 ? 'bg-redline text-card' : r === 4 ? 'bg-marker text-ink' : 'bg-board text-card'}`}>
                      {label}
                    </button>
                  ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {mode === 'mcq' && card.mcq_options && (
        <div className="mt-8">
          <div className="index-card p-8 text-center">
            <p className="font-display font-bold text-xl">{card.front}</p>
          </div>
          <div className="grid gap-2 mt-5">
            {card.mcq_options.choices.map((choice, i) => {
              const answered = picked !== null
              const isAnswer = i === card.mcq_options.answer_index
              const isPicked = i === picked
              return (
                <button key={i} disabled={answered}
                        onClick={async () => {
                          setPicked(i)
                          await sendReview(isAnswer ? 3 : 1, isAnswer, Date.now() - startRef.current)
                        }}
                        className={`rounded-md px-4 py-3 text-left font-medium transition-colors
                          ${!answered ? 'bg-board hover:ring-2 hover:ring-marker'
                            : isAnswer ? 'bg-marker text-ink'
                            : isPicked ? 'bg-redline text-card' : 'bg-board opacity-50'}`}>
                  {choice}
                </button>
              )
            })}
          </div>
          {picked !== null && (
            <div className="mt-5 animate-pop">
              {card.learning_meta?.elaboration && (
                <p className="text-sm text-mist leading-relaxed mb-3">{card.learning_meta.elaboration}</p>
              )}
              <button onClick={advance} className="w-full rounded-md bg-ink ring-1 ring-board text-marker font-display font-bold py-2.5">
              Next →
              </button>
            </div>
          )}
        </div>
      )}

      {mode === 'type' && (
        <div className="mt-8">
          <div className="index-card p-8 text-center">
            <p className="font-display font-bold text-xl">{card.front}</p>
          </div>
          {typeResult === null ? (
            <div className="mt-5 flex gap-2">
              <input autoFocus value={typed} onChange={e => setTyped(e.target.value)}
                     onKeyDown={async e => {
                       if (e.key !== 'Enter') return
                       const ok = levenshteinOk(typed, card.back)
                       setTypeResult(ok)
                       await sendReview(ok ? 3 : 1, ok)
                     }}
                     placeholder="Type the answer, press Enter"
                     className="flex-1 rounded-md bg-board px-4 py-3 placeholder:text-mist focus:outline-none focus:ring-2 focus:ring-marker" />
            </div>
          ) : (
            <div className="mt-5 animate-pop">
              <p className={`font-display font-bold ${typeResult ? 'text-marker' : 'text-redline'}`}>
                {typeResult ? 'Correct!' : 'Not quite.'}
              </p>
              <p className="text-mist text-sm mt-1">Answer: {card.back}</p>
              {card.learning_meta?.elaboration && (
                <p className="text-mist text-sm mt-2 leading-relaxed">{card.learning_meta.elaboration}</p>
              )}
              <button onClick={advance} className="mt-4 w-full rounded-md bg-ink ring-1 ring-board text-marker font-display font-bold py-2.5">
                Next →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Header({ combo, progress, deckId, demo = false }) {
  return (
    <div className="flex items-center justify-between">
      <Link to={demo ? "/demo" : `/decks/${deckId}`} className="text-sm text-mist hover:text-card">✕ End session</Link>
      <span className="font-num text-sm text-mist">{progress}</span>
      <span className={`font-num text-sm ${combo >= 5 ? 'text-marker' : 'text-mist'}`}>
        {combo >= 5 ? `⚡ ${combo}x combo!` : combo > 0 ? `${combo} streak` : '\u00A0'}
      </span>
    </div>
  )
}
