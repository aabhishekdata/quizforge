# QuizForge

A private, invite-only study app for you and your friends. Upload a PDF, DOCX, PPTX, EPUB, or Markdown file and an LLM turns it into a flashcard deck. Study in four modes, earn XP, keep streaks, climb the weekly leaderboard.

## Stack

FastAPI + PostgreSQL + Redis/RQ (async card generation) on the backend, React + Vite + Tailwind on the frontend, and Nginx for production HTTPS/static serving/reverse proxy. Card generation supports Anthropic, OpenAI, and DeepSeek models. Anthropic is the default provider.

## Features

- **Upload → deck**: converts PDF, DOCX, PPTX, EPUB, and MD to Markdown with Microsoft MarkItDown; chunks the Markdown; generates flashcards + MCQs with difficulty tags and source references; live progress while generating
- **Four study modes**: flashcards (flip + self-grade), multiple choice, type-the-answer (fuzzy match), match (pair grid)
- **Gamification**: XP ledger, level curve with titles, combo multiplier, daily-first bonus, day streaks with 2 auto-consumed freeze tokens, 15 achievements, weekly leaderboard (resets Monday)
- **Smart Review**: opt-in per deck; simplified FSRS scheduler with a "due today" count (swap in the `fsrs` PyPI package later — the schema already fits)
- **Sharing**: decks are private by default; share per-deck by username
- **Invite-only auth**: signed session cookies; the first registered account becomes admin and can mint invite codes at `/admin`

## Run locally

Prereqs: Docker + Docker Compose.

```bash
cp .env.example .env         # set SECRET_KEY, POSTGRES_PASSWORD, GENERATION_PROVIDER, and the matching API key
docker compose up --build
```

Provider options:

```bash
# Anthropic, the default
GENERATION_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
GENERATION_MODEL=claude-haiku-4-5
GENERATION_MODEL_HQ=claude-sonnet-4-6

# OpenAI
GENERATION_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_GENERATION_MODEL=gpt-4o-mini
OPENAI_GENERATION_MODEL_HQ=gpt-4o

# DeepSeek
GENERATION_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_GENERATION_MODEL=deepseek-v4-pro
DEEPSEEK_GENERATION_MODEL_HQ=deepseek-v4-pro
DEEPSEEK_THINKING_ENABLED=1
DEEPSEEK_REASONING_EFFORT=max
```

On first boot the API prints a **FIRST-RUN INVITE CODE** to its logs:

```bash
docker compose logs api | grep INVITE
```

For local full-stack Docker use, the bundled Compose file includes a Caddy service for convenience. Production uses Nginx instead.

### Dev mode (hot reload)

```bash
# terminal 1 — db + redis only
docker compose up db redis
# terminal 2 — API
cd backend && pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg2://quizforge:quizforge@localhost:5432/quizforge \
REDIS_URL=redis://localhost:6379/0 uvicorn app.main:app --reload
# terminal 3 — worker
cd backend && python worker.py
# terminal 4 — frontend (proxies /api to :8000)
cd frontend && npm install && npm run dev
```

(For dev mode, expose db/redis ports by adding `ports: ["5432:5432"]` / `["6379:6379"]` to those services, and set `COOKIE_SECURE=0` in the API's environment when testing over plain http.)

## Deploy on Hetzner

1. **Create a server**: Hetzner Cloud → CX22 (2 vCPU / 4GB) → Ubuntu 24.04 → add your SSH key. Enable the Hetzner Cloud Firewall: allow 22, 80, 443 only.
2. **Point DNS**: add an A record for `quiz.yourdomain.com` → the server IP. (HTTPS certificates need this.)
3. **Install Docker + Nginx + Certbot** on the server:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```
4. **Deploy**:
   ```bash
   git clone <your-repo> /opt/quizforge && cd /opt/quizforge
   cp .env.example .env && nano .env      # real secrets here
   docker compose up -d --build db redis api worker
   npm --prefix frontend ci && npm --prefix frontend run build
   sudo rsync -a --delete frontend/dist/ /var/www/quiz.yourdomain.com/html/
   # Configure Nginx to serve that root and proxy /api/ to http://127.0.0.1:8000/api/
   docker compose logs api | grep INVITE   # your first invite code
   ```
5. **Backups**: for app-only recovery use `deploy/full_backup.sh`; for complete VPS recovery use `sudo bash deploy/vps_backup.sh`. Copy `/opt/vps-backups/vps-full-*.tar.gz*` off-server after each run. Hetzner snapshots are still the best whole-machine rollback.
6. **Updating**:
   ```bash
   cd /opt/quizforge
   bash deploy/update_vps.sh
   ```
   The script shows a menu for full deploy, frontend-only deploy, backend-only deploy, or dry-run full deploy.

Costs: ~€4/mo server + LLM usage, depending on the configured provider and model.

## Project layout

```
backend/app/
  main.py            FastAPI app, startup seeding, first-run invite
  models.py          SQLAlchemy models (users, decks, cards, XP ledger, FSRS state…)
  security.py        signed-cookie sessions, bcrypt, admin guard
  routers/           auth, documents (upload+polling), decks (CRUD+share), study, gamification+admin
  services/
    parsing.py       MarkItDown document-to-Markdown conversion + chunking
    generation.py    LLM provider calls, JSON schema, validation
    tasks.py         RQ job: document -> deck
    xp.py            XP rules, levels, streaks, achievements
    fsrs.py          simplified FSRS scheduler
frontend/src/
  App.jsx            auth context, router, nav with XP bar + streak
  pages/             Login, Dashboard, Upload, Deck, Study (4 modes), Leaderboard, Achievements, Admin
docker-compose.yml   db, redis, api, worker, optional local Caddy service; api binds 127.0.0.1:8000 for Nginx
Caddyfile            optional local/alternate Caddy config; production uses Nginx
deploy/backup.sh     nightly pg_dump + uploads archive
deploy/full_backup.sh app recovery backup bundle
deploy/full_restore.sh guarded app restore from a full backup bundle
deploy/update_vps.sh interactive Nginx/VPS deploy helper
deploy/vps_backup.sh complete VPS recovery backup bundle
deploy/vps_restore.sh guarded complete VPS restore helper
```

## Roadmap ideas

- Replace `create_all` with Alembic migrations before the schema evolves
- Swap simplified FSRS for the `fsrs` package
- OCR fallback for scanned PDFs (Tesseract)
- Daily quests, deck-vs-deck challenges
- Rate limiting on login (e.g. slowapi) if you ever open it beyond friends
