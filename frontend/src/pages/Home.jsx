import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <main className="min-h-screen px-4 py-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl flex-col items-center justify-center text-center">
        <p className="mb-6 font-num text-sm uppercase text-marker">Private study decks from your source material</p>
        <h1 className="brand-logo text-6xl font-display font-extrabold leading-none sm:text-8xl md:text-9xl">
          Quiz<span className="marker-block">Forge</span>
        </h1>
        <p className="mt-8 max-w-2xl text-base leading-relaxed text-mist sm:text-lg">
          Turn PDFs, docs, slides, EPUBs, and Markdown into concept-aware flashcards, then study with flashcards, MCQs, typed answers, and matching.
        </p>
        <div className="mt-8 flex w-full max-w-xl flex-col gap-3 sm:flex-row sm:justify-center">
          <Link to="/demo"
                className="rounded-md bg-marker px-6 py-3 text-center font-display font-bold text-ink hover:opacity-90">
            Try the demo deck
          </Link>
          <Link to="/login"
                className="rounded-md bg-board px-6 py-3 text-center font-display font-bold text-card hover:ring-1 hover:ring-marker">
            Sign in
          </Link>
          <Link to="/register"
                className="rounded-md bg-board px-6 py-3 text-center font-display font-bold text-card hover:ring-1 hover:ring-marker">
            Sign up
          </Link>
        </div>
      </div>
    </main>
  )
}
