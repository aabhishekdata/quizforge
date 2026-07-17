# QuizForge Knowledge Base

Last updated: 2026-07-05

## 1. Project Overview

QuizForge is a private, invite-only study application for converting source documents into high-quality flashcard decks. Users upload educational material, the backend extracts and chunks text, a configured LLM generates a concept-aware deck, and users study through multiple modes with XP, streaks, achievements, and optional spaced repetition.

Core product promise:

- Upload a PDF, DOCX, PPTX, EPUB, or Markdown file.
- Build a deck that teaches the subject, not just the document.
- Study with flashcards, multiple choice, typed answers, and matching.
- Track motivation through XP, streaks, achievements, leaderboards, and Smart Review.
- Share decks with users or groups, controlled by admins.
- Import existing decks from JSON or CSV and export decks for backup or spreadsheet/tool interchange.

Current production target:

- Domain: `quizforge.aabhishek.in`
- VPS: Hetzner Ubuntu server at `157.90.167.86`
- Frontend: React/Vite static build served by Nginx
- Backend: FastAPI in Docker, published only to `127.0.0.1:8000`
- Data services: PostgreSQL and Redis in Docker
- HTTPS: Certbot-managed Nginx certificate

## 2. Key Concepts And Terminology

### Product Concepts

- **Deck**: A collection of generated or manually created cards owned by a user.
- **Subject**: A per-user study domain such as AIGP or CDMP. Decks can belong to one subject.
- **Card**: A study item with `front`, `back`, difficulty, type, optional MCQ options, and learning metadata.
- **Document**: An uploaded source file that moves through parsing and generation states.
- **Subject skeleton**: A document-level concept map generated before card generation. It contains first principles, core concepts, dependencies, and misconceptions.
- **First principle**: A fundamental idea that explains or derives other concepts in the subject.
- **Core concept**: A teachable unit linked to exactly one first principle and optionally dependent on other concepts.
- **Misconception**: A specific wrong belief used to create stronger MCQ distractors.
- **Smart Review**: Per-deck opt-in spaced repetition powered by a simplified FSRS-style scheduler.
- **Invite code**: Required for registration. The first registered user becomes admin.
- **Admin**: A user with permission to mint invite codes, create groups, manage group members, and share decks.
- **Group sharing**: Admin-mediated sharing of a deck to all members of a study group.

### Generation Concepts

- **Pass 0**: Build a subject skeleton once per document from an outline of headings and lead sentences.
- **Pass 1**: Generate cards per chunk using the subject skeleton and previous card fronts to avoid duplicates.
- **High-quality generation**: A user-selectable upload option that chooses the high-quality model setting for the configured provider.
- **Card type distribution**:
  - Recall: definitions, facts, terms
  - Why: mechanism and causation
  - Application: scenario-based use
  - Contrast: comparing concepts and choosing between them
  - Derivation: reconstructing a concept from first principles

### Infrastructure Concepts

- **API container**: FastAPI app served by Uvicorn on container port `8000`.
- **Worker container**: RQ worker that processes document generation jobs from Redis.
- **Redis**: Queue backend for generation jobs.
- **PostgreSQL**: Main relational database.
- **Nginx**: Public web server for static frontend and `/api/` reverse proxy.
- **Certbot**: Issues and renews HTTPS certificate for the subdomain.

## 3. Architecture

### Runtime Flow

1. User signs in through `/api/auth/login` or registers with an invite code.
2. User uploads a document from the React frontend.
3. FastAPI validates file type and size, stores it under `UPLOAD_DIR`, creates a `Document` row, and enqueues an RQ job.
4. Worker parses the file into sections.
5. Worker chunks sections into LLM-sized chunks.
6. Worker calls the LLM once to create a subject skeleton.
7. Worker calls the LLM per chunk to create cards.
8. Cards are cleaned, validated, deduplicated against previous fronts, and written to PostgreSQL.
9. Document status changes to `ready` or `failed`.
10. User studies the generated deck through one of four modes.
11. Reviews create review logs, XP events, streak updates, achievements, and optional Smart Review scheduling.

### Service Layout

```text
Browser
  -> Nginx static frontend
  -> Nginx /api proxy
  -> FastAPI container on 127.0.0.1:8000
  -> PostgreSQL container
  -> Redis container
  -> RQ worker container
  -> LLM provider API
```

### Source Layout

```text
backend/app/
  config.py          Settings and provider configuration
  database.py        SQLAlchemy engine/session setup
  main.py            FastAPI app, startup seeding, first-run invite bootstrap
  models.py          SQLAlchemy entities
  schemas.py         Pydantic request/response models
  security.py        Password hashing, signed cookie sessions, admin guard
  routers/
    auth.py          Register, login, logout, current user
    documents.py     Upload, list, poll document status
    decks.py         Subject CRUD, deck CRUD, card CRUD, sharing, group sharing, import/export
    study.py         Study sessions, reviews, completion
    gamification.py  Leaderboard, achievements, admin invites and groups
  services/
    parsing.py       MarkItDown document-to-Markdown conversion and chunking
    deck_io.py       JSON/CSV deck import and export normalization
    generation.py    LLM prompts, provider calls, JSON repair, card cleaning
    tasks.py         RQ document-to-deck job
    xp.py            XP, levels, streaks, achievements
    fsrs.py          Simplified FSRS-style scheduler
backend/
  worker.py          RQ worker entrypoint
  requirements.txt   Python dependencies
frontend/src/
  App.jsx            Auth context, routing, nav, themes
  lib/api.js         Fetch wrapper with cookie credentials
  pages/             Login, dashboard, upload, deck, study, admin, leaderboard, badges
deploy/
  backup.sh          pg_dump and uploads archive
  update_vps.sh      interactive Nginx/VPS deploy helper
docker-compose.yml   db, redis, api, worker, optional local Caddy service; api binds 127.0.0.1:8000 for Nginx
Caddyfile            Alternative/local Caddy config; production uses Nginx
```

## 4. Domain Model

### Main Entities

- **User**
  - `username`, `password_hash`, `is_admin`
  - Owns decks
  - Has XP events and optional streak state

- **InviteCode**
  - `code`, `created_by`, `used_by`, `used_at`
  - Registration requires an unused invite code
  - First user registered becomes admin

- **Document**
  - `owner_id`, `filename`, `filetype`, `stored_path`
  - Status: `pending`, `parsing`, `generating`, `ready`, `failed`
  - Progress and error strings support frontend polling

- **Deck**
  - `owner_id`, optional `document_id`, `title`, `description`
  - Optional `subject_id`
  - `is_shared`, `smart_review`
  - Contains cards
  - Can be imported from JSON/CSV or exported as JSON/CSV

- **Subject**
  - `owner_id`, `name`, `description`
  - Unique per owner by name.
  - Deleting a subject leaves its decks uncategorized.
  - Shared decks keep and display the owner's subject name.

- **Card**
  - `front`, `back`, `difficulty`, `card_type`
  - Optional `mcq_options`
  - Optional `learning_meta` JSON
  - Optional `source_ref`

- **DeckShare**
  - Per-user deck sharing.

- **StudyGroup**
  - Admin-created group.

- **StudyGroupMember**
  - User membership in a group.

- **DeckGroupShare**
  - Deck shared to a group by an admin.

- **CardReview**
  - Per-user, per-card scheduling state for Smart Review.

- **ReviewLog**
  - Append-only record of each study review.

- **XPEvent**
  - Append-only XP ledger. Leaderboards and levels derive from this table.

- **Streak**
  - Tracks current streak, longest streak, last study date, and freeze tokens.

- **Achievement / UserAchievement**
  - Seeded achievement catalog and earned achievement records.

## 5. LLM Generation Architecture

### Provider Support

The app supports three provider families:

- Anthropic
  - Default provider in settings.
  - Uses `ANTHROPIC_API_KEY`.
  - Default model settings: `GENERATION_MODEL`, `GENERATION_MODEL_HQ`.

- OpenAI
  - Uses `OPENAI_API_KEY`.
  - Optional `OPENAI_BASE_URL`.
  - Model settings: `OPENAI_GENERATION_MODEL`, `OPENAI_GENERATION_MODEL_HQ`.

- DeepSeek
  - Uses OpenAI-compatible client.
  - Uses `DEEPSEEK_API_KEY`.
  - Default base URL: `https://api.deepseek.com`.
  - Model settings: `DEEPSEEK_GENERATION_MODEL`, `DEEPSEEK_GENERATION_MODEL_HQ`.
  - Current intended production model: `deepseek-v4-pro`.
  - Thinking enabled through extra body when `DEEPSEEK_THINKING_ENABLED=1`.
  - Reasoning effort normalized to `high` or `max`, defaulting to `max`.

### Prompting Principles

The generation system follows these patterns:

- Ask for structured JSON only.
- Separate document-level understanding from chunk-level generation.
- Build a subject skeleton before generating cards.
- Inject the skeleton into every chunk prompt.
- Track previous card fronts to reduce duplicates.
- Prefer fewer strong cards over padded weak cards.
- Focus cards on understanding the material, not trivia about the document.
- Require medium and hard cards to include elaboration.
- Use misconceptions for MCQ distractors.
- Avoid raw URLs and links in cards.
- Store enrichment in `learning_meta` rather than overloading `front` and `back`.

### Pass 0: Subject Skeleton

Input:

- Document title
- File type
- Outline of section labels and lead sentences

Output:

- Subject name
- Audience level
- First principles
- Core concepts
- Concept dependencies
- Misconceptions

Validation:

- First principles are capped at 8.
- Concepts are capped at 24.
- Concept dependencies are filtered to known concept IDs.
- Concepts map only to known first-principle IDs.

### Pass 1: Card Generation

Input:

- Subject skeleton JSON
- Previous generated card fronts
- Current chunk text
- Source label
- Chunk index and total chunks
- Requested card count

Output card fields:

- `front`
- `back`
- `card_type`
- `difficulty`
- `first_principle`
- `elaboration`
- `connections`
- `misconception_note`
- `real_world_example`
- `mcq`
- `source`

Validation:

- Drop non-dict card objects.
- Require non-empty `front` and `back`.
- Normalize and deduplicate card fronts.
- Clamp text lengths.
- Normalize card type to `recall`, `why`, `application`, `contrast`, or `derivation`.
- Normalize difficulty to `easy`, `medium`, or `hard`.
- Drop unknown first-principle and concept IDs.
- Accept MCQ only when it has exactly 4 choices and one valid answer index.
- Store learning fields in `learning_meta`.
- Use `source_ref` from source label.

## 6. Document Parsing And Chunking

Supported file types:

- PDF, DOCX, PPTX, and EPUB are converted to Markdown with Microsoft MarkItDown.
- Markdown is read directly as UTF-8 and follows the same sectioning/chunking path.
- Generated Markdown headings become section labels for source references and chunk context.

Limits and behavior:

- Upload limit defaults to 25 MB.
- PDF page limit defaults to 150 pages.
- Chunk size defaults to 8000 characters.
- Chunk overlap is 400 characters for oversized sections.
- Minimum useful chunk size is 300 characters.
- Scanned PDFs still need an OCR-enabled conversion path before they can produce useful cards.

## 7. API Surface

### Auth

- `POST /api/auth/register`
  - Requires username, password, invite code.
  - First account becomes admin.

- `POST /api/auth/login`
  - Sets signed HTTP-only cookie.

- `POST /api/auth/logout`
  - Clears session cookie.

- `GET /api/auth/me`
  - Returns current user, XP, level, progress, streak, and admin status.

### Documents

- `POST /api/documents`
  - Multipart upload.
  - Form field: `high_quality`.
  - Form field: `upload_code`; must match `settings.upload_unlock_code`.
  - Enqueues generation job through Redis/RQ.
  - If Redis enqueue fails, falls back to an in-process FastAPI background task so local/dev upload does not return a 500.
  - VPS production should still run Redis and the worker service; the fallback is resilience, not the normal production execution path.

- `GET /api/documents`
  - Lists current user's documents.

- `GET /api/documents/{doc_id}`
  - Polls document status.

### Decks And Cards

- `GET /api/subjects`
  - Lists the current user's subjects with deck counts.

- `POST /api/subjects`
  - Creates a subject for the current user.

- `PATCH /api/subjects/{subject_id}`
  - Renames or updates a current-user subject.

- `DELETE /api/subjects/{subject_id}`
  - Deletes a current-user subject and clears `subject_id` on its decks.

- `GET /api/decks`
  - Lists owned, user-shared, and group-shared decks.
  - Deck responses include `subject_id` and `subject_name`.

- `POST /api/decks`
  - Creates manual deck.
  - Optional `subject_id` or `subject_name`.

- `POST /api/decks/import`
  - Multipart deck import.
  - Accepts `.json` and `.csv`.
  - JSON is the canonical QuizForge round-trip format.
  - JSON subject metadata is matched or created by subject name unless an explicit subject is supplied.
  - CSV accepts `front/back`, `question/answer`, or `term/definition` columns.
  - Optional CSV fields: `difficulty`, `card_type`, `source_ref`, `learning_meta`, `mcq_options`.

- `GET /api/decks/{deck_id}`
  - Gets accessible deck.

- `GET /api/decks/{deck_id}/export.json`
  - Downloads an accessible deck in canonical QuizForge JSON format.
  - Includes deck metadata and full card fields, including learning metadata and MCQ options.

- `GET /api/decks/{deck_id}/export.csv`
  - Downloads accessible deck cards as CSV.
  - Keeps structured fields as compact JSON strings inside CSV columns.

- `PATCH /api/decks/{deck_id}`
  - Owner-only edit of title, description, or Smart Review flag.
  - Owner can move a deck to a subject by `subject_id`, create/match by `subject_name`, or clear to uncategorized.

- `DELETE /api/decks/{deck_id}`
  - Owner-only deletion.

- `POST /api/decks/{deck_id}/share`
  - Admin-only share to username.

- `POST /api/decks/{deck_id}/share-group`
  - Admin-only share to group.

- `GET /api/decks/{deck_id}/cards`
  - Lists cards for accessible deck.

- `POST /api/decks/{deck_id}/cards`
  - Owner-only manual card creation.

- `PATCH /api/decks/{deck_id}/cards/{card_id}`
  - Owner-only card edit.

- `DELETE /api/decks/{deck_id}/cards/{card_id}`
  - Owner-only card deletion.

### Public Demo

- `GET /api/demo/decks/mental-models`
  - Public, no-auth demo deck metadata.
  - Used by `/demo`.

- `GET /api/demo/decks/mental-models/cards`
  - Public, no-auth demo cards.
  - Returns the fixed Mental Models sample deck.

- `GET /api/demo/study/mental-models/session`
  - Public, no-auth study session for the demo deck.
  - Query: `mode`, `limit`.
  - Used by the same frontend study UI as authenticated decks.
  - Does not write review logs, XP, streaks, or achievements.

### Study

- `GET /api/study/{deck_id}/session`
  - Query: `mode`, `limit`, `smart`.
  - Returns shuffled cards.
  - MCQ mode filters to cards with MCQ options.
  - Smart mode returns due cards only when enabled.

- `POST /api/study/review`
  - Logs review.
  - Awards XP.
  - Updates streak.
  - Schedules Smart Review if enabled.
  - Checks achievements.

- `POST /api/study/session/complete`
  - Awards deck completion XP.
  - Grants perfectionist achievement when applicable.

### Gamification And Admin

- `GET /api/leaderboard`
  - Weekly XP ranking.

- `GET /api/achievements`
  - Achievement list and earned status.

- `POST /api/admin/invites`
  - Admin-only invite creation.

- `GET /api/admin/invites`
  - Admin-only invite listing.

- `GET /api/admin/groups`
  - Admin-only group listing.

- `POST /api/admin/groups`
  - Admin-only group creation.

- `POST /api/admin/groups/{group_id}/members`
  - Admin-only add member by username.

- `DELETE /api/admin/groups/{group_id}/members/{username}`
  - Admin-only remove member.

## 8. Frontend UX And Workflows

### Authentication

- Unauthenticated users see the public home page, demo deck, login, register, and reset routes.
- Registration requires an invite code.
- Auth state is loaded from `/api/auth/me`.
- Sessions use cookie credentials in `fetch`.

### Navigation

Authenticated routes:

- Decks dashboard
- Upload
- Leaderboard
- Badges
- Admin page for admins only

### Upload Workflow

1. User opens the Upload tab.
2. Upload tab remains visible but starts in a locked state until the user enters `Ilovequizforge`.
3. Unlock state is stored in browser local storage.
4. User optionally chooses an existing subject or creates a new subject.
5. User optionally enables high-quality generation.
6. Frontend posts multipart form to `/api/documents` with `upload_code`.
7. Backend rejects uploads with HTTP 403 if `upload_code` does not match `settings.upload_unlock_code`.
8. Backend stores the upload and enqueues the document generation job through Redis/RQ.
9. If Redis enqueue is unavailable in local/dev, backend schedules the same job as a FastAPI background task.
10. Frontend polls `/api/documents/{id}` every 2 seconds.
11. On `ready`, user is redirected to the dashboard.
12. On `failed`, error is displayed and the user can try another file.

### Deck Workflow

- Dashboard groups decks by subject and provides an All subjects / subject / Uncategorized filter.
- Dashboard can create subjects inline.
- Dashboard has an **Import deck** button for existing JSON or CSV flashcard decks.
- Deck page shows title, card count, owner/share state, and study modes.
- Deck page shows the deck subject.
- Deck owners can move a deck between subjects or Uncategorized.
- Deck page has **Export JSON** and **Export CSV** buttons.
- Owner can toggle Smart Review.
- Owner can edit or delete cards.
- Admin can share deck to a user or a group.
- Cards display elaboration and real-world example when available.

### Public Demo Workflow

- Logged-out `/` is a public front page with a large QuizForge logo, a short app introduction, and links to demo, sign in, and sign up.
- `/demo` is public and bypasses the login gate.
- Login page includes a visible **Try the demo deck** callout.
- `/login`, `/register`, and `/reset` route directly to the corresponding auth form mode.
- Demo uses the fixed Mental Models deck served by `/api/demo`.
- Demo deck overview reuses `Deck.jsx` with `demo` mode.
- Demo flashcard, MCQ, type-answer, and match screens reuse `Study.jsx` with `demo` mode.
- Demo mode hides write actions such as export, subject moves, Smart Review toggles, card edits, and admin sharing.
- Demo mode suppresses review logging, XP, streaks, achievements, and session completion writes.
- The UI should visually match real deck/study screens, especially the flashcard reveal layout.

### Deck Import And Export Workflow

- Import is a lightweight deck creation path, separate from document generation.
- JSON export is preferred for backups and QuizForge-to-QuizForge migration.
- JSON export includes the deck subject name.
- CSV export is preferred for spreadsheet inspection and simple external tools.
- Imported decks are owned by the current user.
- Imported JSON subjects are matched case-insensitively or created for the importing user.
- Import does not preserve source documents, study history, review logs, shares, or per-user FSRS state.
- Export is available for any accessible deck, including shared decks.
- Import validation caps deck size at 5000 cards.
- Invalid or blank card rows are skipped; import fails if no valid cards remain.

### Study Modes

- **Flashcard**
  - Shows question first.
  - Revealed answer area scrolls internally and adapts to viewport height.
  - Rating buttons: Again, Hard, Good, Easy.

- **Multiple choice**
  - Requires cards with `mcq_options`.
  - Shows answer coloring after pick.
  - Displays elaboration after answer.

- **Type answer**
  - Uses a client-side Levenshtein similarity check.
  - Accepts close answers within a rough 20 percent edit distance.

- **Match**
  - Builds paired front/back tiles from up to 6 cards.
  - Awards reviews as pairs are matched.
  - Speed can affect XP through backend review logic.

### Themes

Theme selection is stored in `localStorage` under `qf_theme` and applied to `document.documentElement.dataset.theme`.

Available themes:

- `classic`
- `high-contrast`
- `color-blind`
- `soft-light`
- `spectrum`

Spectrum palette:

- `#003d5c`
- `#464c89`
- `#954e9b`
- `#dd4d88`
- `#ff6b59`
- `#ffa600`

Important UI convention:

- Card text colors are theme variables, not fixed Tailwind text colors.
- Revealed flashcard content uses viewport-aware sizing and an internal scroll area to avoid overflowing off screen.

## 9. Gamification Rules

### XP

- Correct review: 5 XP.
- Incorrect review: 2 XP.
- Deck completion: 50 XP.
- First study of day: 20 XP.
- Combo threshold: 5 correct in a row.
- Combo multiplier: 1.5.
- Match speed bonus: up to 30 XP.

### Levels

Level XP is cumulative:

```text
sum(int(100 * (n ** 1.5)) for n in range(1, level))
```

Level titles:

- Level 1: Novice
- Level 5: Apprentice
- Level 10: Scholar
- Level 15: Adept
- Level 20: Sage
- Level 30: Grandmaster

### Streaks

- Reviewing touches the streak.
- Consecutive next-day review increments streak.
- One missed day can be bridged by an auto-consumed freeze token.
- New users start with 2 freeze tokens.

### Achievements

Seeded achievements include first deck, review count, perfect sessions, streak milestones, time-of-day study, comeback, level milestones, match mastery, uploader, sharer, Smart Review start, and 1000 XP.

## 10. Production Deployment Runbook

This section consolidates the working deployment path from the Hetzner setup session.

### 10.1 DNS

Ensure DNS points the subdomain to the VPS:

```text
A    quizforge    157.90.167.86
```

This resolves:

```text
quizforge.aabhishek.in -> 157.90.167.86
```

### 10.2 SSH And Base Packages

```bash
ssh abhi@157.90.167.86
sudo apt update
sudo apt upgrade -y
sudo apt install -y nginx certbot python3-certbot-nginx git curl ufw fail2ban rsync
```

### 10.3 Docker

If Docker is already installed, do not rerun the install script. If it is not installed:

```bash
curl -fsSL https://get.docker.com | sh
```

Add user to Docker group:

```bash
sudo usermod -aG docker abhi
```

Log out and SSH back in, or use `sudo docker` until group membership refreshes.

### 10.4 Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Hetzner Cloud Firewall should allow only:

- 22
- 80
- 443

### 10.5 Project Location

In the observed deployment, the copied source was nested:

```text
/opt/quizforge/quizforge
```

The active Compose directory is the directory containing `docker-compose.yml`:

```bash
cd /opt/quizforge/quizforge
ls docker-compose.yml
```

If `docker compose` says `no configuration file provided: not found`, you are in the wrong directory or the compose file is missing.

### 10.6 Environment File

Create:

```bash
cd /opt/quizforge/quizforge
nano .env
```

Required pattern:

```env
SECRET_KEY=replace_with_long_random_hex
POSTGRES_PASSWORD=replace_with_url_safe_password

GENERATION_PROVIDER=deepseek
DEEPSEEK_API_KEY=replace_with_rotated_key
DEEPSEEK_GENERATION_MODEL=deepseek-v4-pro
DEEPSEEK_GENERATION_MODEL_HQ=deepseek-v4-pro
DEEPSEEK_THINKING_ENABLED=1
DEEPSEEK_REASONING_EFFORT=max

COOKIE_SECURE=1
UPLOAD_DIR=/data/uploads
```

Generate safe random values:

```bash
openssl rand -hex 32
openssl rand -hex 16
```

Important:

- Use URL-safe `POSTGRES_PASSWORD` characters only: letters and numbers are safest.
- Avoid `#`, `$`, `@`, `/`, `:` in `POSTGRES_PASSWORD`.
- If a `.env` value contains `$`, Docker Compose may try to expand it.
- API keys exposed in logs or chat should be rotated.

### 10.7 Compose File

The production Nginx setup does not need the Caddy service. A minimal Compose file:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: quizforge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-quizforge}
      POSTGRES_DB: quizforge
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U quizforge"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

  api:
    build: ./backend
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg2://quizforge:${POSTGRES_PASSWORD:-quizforge}@db:5432/quizforge
      REDIS_URL: redis://redis:6379/0
      UPLOAD_DIR: /data/uploads
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - uploads:/data/uploads
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

  worker:
    build: ./backend
    command: python worker.py
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg2://quizforge:${POSTGRES_PASSWORD:-quizforge}@db:5432/quizforge
      REDIS_URL: redis://redis:6379/0
      UPLOAD_DIR: /data/uploads
    volumes:
      - uploads:/data/uploads
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
  uploads:
```

VPS notes:

- Preferred deploy path is the interactive helper:
  `bash deploy/update_vps.sh`
- The helper offers full deploy, frontend-only deploy, backend-only deploy, and dry-run full deploy choices.
- Non-interactive flags are available: `--full`, `--frontend-only`, `--backend-only`, `--dry-run`, `--skip-npm-ci`, and `--skip-smoke`.
- Rebuild both `api` and `worker` after dependency changes such as MarkItDown:
  `docker compose up -d --build api worker`
- Redis and `worker` should remain enabled on the VPS. Upload generation normally runs through Redis/RQ.
- The API has an inline background-task fallback if Redis enqueue fails. Treat this as a local/dev safety net and outage resilience; do not rely on it as the production worker model.
- Public demo routes are served by the API under `/api/demo/*` and the SPA under `/demo`, so the Nginx `/api/` proxy and `try_files ... /index.html` SPA fallback are sufficient.
- The demo deck is static application data and does not require database rows, migrations, uploads storage, Redis, or login.
- MarkItDown conversion runs inside the `api` or `worker` container that processes the generation job. The backend image must be rebuilt after `backend/requirements.txt` changes.

If using an override instead of inline ports:

```bash
cat > docker-compose.override.yml <<'EOF'
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"
EOF
```

Start backend:

```bash
cd /opt/quizforge/quizforge
sudo docker compose config
sudo docker compose up -d --build db redis api worker
sudo docker compose ps
curl http://127.0.0.1:8000/api/health
```

Expected:

```json
{"ok":true}
```

### 10.8 Frontend Build

Use Node 22 on the VPS:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

Clean install and build:

```bash
cd /opt/quizforge/quizforge/frontend
rm -rf node_modules package-lock.json
npm pkg set devDependencies.vite="^5.3.4"
npm pkg set devDependencies.@vitejs/plugin-react="^4.3.1"
npm install
npm run build
```

If `npm pkg set` fails on the scoped package name, edit `package.json` manually and keep:

```json
"devDependencies": {
  "@vitejs/plugin-react": "^4.3.1",
  "autoprefixer": "^10.4.19",
  "postcss": "^8.4.39",
  "tailwindcss": "^3.4.6",
  "vite": "^5.3.4"
}
```

Publish frontend:

```bash
sudo mkdir -p /var/www/quizforge.aabhishek.in/html
sudo rsync -a --delete dist/ /var/www/quizforge.aabhishek.in/html/
sudo chown -R www-data:www-data /var/www/quizforge.aabhishek.in
sudo chmod -R 755 /var/www/quizforge.aabhishek.in
```

Avoid:

```bash
npm audit fix --force
```

It can upgrade Vite across major versions and break the deploy.

Important production note:

- The current production Compose file contains only `db`, `redis`, `api`, and `worker`.
- Frontend changes are not deployed by `docker compose up -d --build`.
- For UI changes, run `npm run build`, then copy `frontend/dist/` to the Nginx root.
- Current Nginx root is:

```text
/var/www/quizforge.aabhishek.in/html
```

Verification after publishing:

```bash
grep -R "Import deck" -n /var/www/quizforge.aabhishek.in/html/assets | head
curl -s https://quizforge.aabhishek.in | grep -o 'assets/index-[^"]*\.js'
```

### 10.9 Nginx Hardening

Use `sudo tee` for files under `/etc`; `sudo cat > file` does not elevate shell redirection.

```bash
sudo mkdir -p /etc/nginx/snippets

cat <<'EOF' | sudo tee /etc/nginx/snippets/security-headers.conf > /dev/null
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header X-XSS-Protection "0" always;
EOF
```

Hide Nginx version:

```bash
sudo sed -i 's/# server_tokens off;/server_tokens off;/' /etc/nginx/nginx.conf
grep -q "server_tokens off;" /etc/nginx/nginx.conf || sudo sed -i '/http {/a \    server_tokens off;' /etc/nginx/nginx.conf
sudo nginx -t
```

### 10.10 Nginx Site

```bash
sudo rm -f /etc/nginx/sites-enabled/default

cat <<'EOF' | sudo tee /etc/nginx/sites-available/quizforge.aabhishek.in > /dev/null
server {
    listen 80;
    listen [::]:80;

    server_name quizforge.aabhishek.in;

    root /var/www/quizforge.aabhishek.in/html;
    index index.html;

    client_max_body_size 30M;

    include snippets/security-headers.conf;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~ /\.(?!well-known) {
        deny all;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/quizforge.aabhishek.in /etc/nginx/sites-enabled/quizforge.aabhishek.in
sudo nginx -t
sudo systemctl reload nginx
curl -I http://quizforge.aabhishek.in
curl http://quizforge.aabhishek.in/api/health
```

### 10.11 HTTPS

```bash
sudo certbot --nginx -d quizforge.aabhishek.in
```

Choose redirect when prompted.

After Certbot modifies the Nginx config, add HSTS to the HTTPS server block:

```nginx
include snippets/security-headers.conf;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

Do not include custom SSL hardening snippets if Certbot's `options-ssl-nginx.conf` already contains the same directives. Duplicate directives such as `ssl_session_timeout` will make `nginx -t` fail.

Verify:

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I https://quizforge.aabhishek.in
curl https://quizforge.aabhishek.in/api/health
sudo certbot renew --dry-run
```

### 10.12 First Invite Code

Preferred log method:

```bash
cd /opt/quizforge/quizforge
sudo docker compose logs api | grep INVITE
```

If logs do not show the invite, query Postgres:

```bash
sudo docker compose exec -T db psql -U quizforge -d quizforge -c \
"select code, used_by, created_at from invite_codes order by created_at desc;"
```

If no unused invite exists:

```bash
CODE=$(openssl rand -hex 4 | tr '[:lower:]' '[:upper:]')

sudo docker compose exec -T db psql -U quizforge -d quizforge -c \
"insert into invite_codes (code, created_by, used_by, used_at, created_at) values ('$CODE', null, null, null, now()) returning code;"
```

Open:

```text
https://quizforge.aabhishek.in
```

Register with the invite code. The first account becomes admin.

## 11. Deployment Troubleshooting Patterns

### Docker Compose Cannot Find Config

Symptom:

```text
no configuration file provided: not found
```

Cause:

- Running `docker compose` from a directory without `docker-compose.yml`.
- In this deployment, `/opt/quizforge` was one level above the real app folder.

Fix:

```bash
cd /opt/quizforge/quizforge
ls docker-compose.yml
sudo docker compose ps
```

### Compose Warns About `$pubH`

Symptom:

```text
WARN The "pubH" variable is not set. Defaulting to a blank string.
```

Cause:

- A `.env` value contains `$pubH...`.
- Compose interprets `$pubH` as a variable expansion.

Fix:

```bash
grep -n '\$[A-Za-z_]' .env
nano .env
```

Wrap the value in single quotes, or rotate to a value without `$`.

### API 502 Through Nginx

Symptom:

```text
502 Bad Gateway
```

Diagnosis:

```bash
cd /opt/quizforge/quizforge
sudo docker compose ps
curl -v http://127.0.0.1:8000/api/health
sudo docker compose logs api --tail=120
```

Common causes:

- API container is restarting.
- API host port is not published.
- API cannot connect to Postgres.

### API Restarting Due To Postgres Password

Symptom:

```text
FATAL: password authentication failed for user "quizforge"
```

Common causes:

- `POSTGRES_PASSWORD` changed after the Postgres volume was initialized.
- Password contains URL-special characters such as `#`.

Fresh deploy fix:

```bash
cd /opt/quizforge/quizforge
nano .env
# set POSTGRES_PASSWORD to a URL-safe hex value
sudo docker compose down
sudo docker volume rm quizforge_pgdata
sudo docker compose up -d --build db redis api worker
```

Do not delete the Postgres volume after real users/decks exist unless restoring from backup.

### API Running But Localhost 8000 Refuses Connection

Symptom:

```text
curl: (7) Failed to connect to 127.0.0.1 port 8000
```

Check `docker compose ps`. If API shows only `8000/tcp`, it is not published to the host.

Expected:

```text
127.0.0.1:8000->8000/tcp
```

Fix:

```bash
cat > docker-compose.override.yml <<'EOF'
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"
EOF

sudo docker compose up -d api
```

### Vite Permission Denied

Symptom:

```text
sh: 1: vite: Permission denied
```

Cause:

- `node_modules` copied from Windows to Linux.

Fix:

```bash
cd /opt/quizforge/quizforge/frontend
sudo chown -R abhi:abhi /opt/quizforge/quizforge/frontend
rm -rf node_modules
npm install
npm run build
```

### Vite Requires Newer Node

Symptom:

```text
Vite requires Node.js version 20.19+ or 22.12+
ReferenceError: CustomEvent is not defined
```

Fix:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
```

### `npm audit fix --force` Broke Dependency Tree

Symptom:

```text
ERESOLVE unable to resolve dependency tree
Found: vite@8.1.3
Could not resolve dependency: @vitejs/plugin-react peer vite ^4 || ^5 || ^6 || ^7
```

Fix:

```bash
cd /opt/quizforge/quizforge/frontend
rm -rf node_modules package-lock.json
npm pkg set devDependencies.vite="^5.3.4"
npm pkg set devDependencies.@vitejs/plugin-react="^4.3.1"
npm install
npm run build
```

### Frontend Build Updated But UI Does Not Change

Symptom:

- Backend containers rebuild successfully.
- New UI text exists in `frontend/src` and `frontend/dist`.
- Browser still shows the old UI.

Cause:

- Production Nginx serves static files from `/var/www/quizforge.aabhishek.in/html`, not directly from `frontend/dist`.
- Docker Compose does not include a frontend service in the active production setup.
- Browser cache can also keep an old asset briefly.

Diagnosis:

```bash
cd /opt/quizforge/quizforge
grep -R "Import deck" -n frontend/src frontend/dist | head
sudo nginx -T | grep -E "root |alias "
ls -lah /var/www/quizforge.aabhishek.in/html/assets | head
grep -R "Import deck" -n /var/www/quizforge.aabhishek.in/html/assets | head
```

Fix:

```bash
cd /opt/quizforge/quizforge/frontend
npm run build
sudo rsync -a --delete dist/ /var/www/quizforge.aabhishek.in/html/
sudo systemctl restart nginx
```

Then hard-refresh the browser with `Ctrl+F5`, or open the site with a cache-busting query such as:

```text
https://quizforge.aabhishek.in/?v=2
```

### Nginx Permission Denied While Writing Config

Symptom:

```text
-bash: /etc/nginx/snippets/security-headers.conf: Permission denied
```

Cause:

- `sudo cat > file` does not elevate shell redirection.

Fix:

```bash
cat <<'EOF' | sudo tee /etc/nginx/snippets/security-headers.conf > /dev/null
# content here
EOF
```

### Duplicate SSL Directive

Symptom:

```text
"ssl_session_timeout" directive is duplicate
```

Cause:

- Custom SSL snippet duplicates Certbot's SSL options.

Fix:

- Remove `include snippets/ssl-hardening.conf;` from the HTTPS server block.
- Keep security headers and HSTS.

## 12. Security And Operations

### Secrets

- `.env` contains secrets and should not be committed.
- Do not paste API keys, database passwords, or full `.env` output into public places.
- Rotate API keys that appear in logs or chat.
- Use URL-safe database passwords to avoid URI parsing failures.

### Session Security

- Sessions are signed with `SECRET_KEY`.
- Cookies are HTTP-only.
- `COOKIE_SECURE=1` is required for HTTPS production.
- Use `COOKIE_SECURE=0` only for plain HTTP local development.

### Network Exposure

- Public: Nginx on ports 80 and 443.
- SSH: port 22.
- Private localhost only: API on `127.0.0.1:8000`.
- Internal Docker network: PostgreSQL and Redis.

### Backups

Legacy backup script behavior:

- Creates `/opt/quizforge-backups`.
- Dumps PostgreSQL with `pg_dump`.
- Archives uploads volume.
- Deletes `.gz` backups older than 14 days.

For app-only disaster recovery:

```bash
cd /opt/quizforge/quizforge
sudo bash deploy/full_backup.sh
```

It creates `/opt/quizforge-backups/quizforge-full-YYYYmmdd-HHMMSS.tar.gz` plus a `.sha256` checksum.

The full backup includes:

- PostgreSQL dump
- Uploads volume
- `.env`
- Nginx site config
- Certbot/Let's Encrypt config, when readable
- repo working tree, excluding bulky cache/build folders
- crontab and server metadata

Fresh VPS restore pattern:

```bash
sudo mkdir -p /opt/quizforge-backups
sudo cp quizforge-full-YYYYmmdd-HHMMSS.tar.gz /opt/quizforge-backups/
sudo bash deploy/full_restore.sh --install-prereqs /opt/quizforge-backups/quizforge-full-YYYYmmdd-HHMMSS.tar.gz
```

The restore script prompts for `RESTORE` unless `--yes` is supplied. It can overwrite app files, PostgreSQL data, uploads, Nginx config, and Certbot config.

For complete VPS recovery, use provider snapshots plus the VPS backup script:

```bash
cd /opt/quizforge/quizforge
sudo bash deploy/vps_backup.sh
```

It creates:

```text
/opt/vps-backups/vps-full-YYYYmmdd-HHMMSS.tar.gz
/opt/vps-backups/vps-full-YYYYmmdd-HHMMSS.tar.gz.sha256
```

The VPS backup includes:

- `/etc`
- `/home`
- `/root`
- `/opt`
- `/srv`
- `/var/www`
- `/usr/local`
- common non-Docker database directories: `/var/lib/mysql`, `/var/lib/postgresql`, `/var/lib/redis`
- all Docker named volumes
- Docker/container/image/network metadata
- package lists
- crontabs
- systemd metadata
- firewall metadata
- QuizForge logical `pg_dump` when `/opt/quizforge/quizforge` exists

Optional large Docker image archive:

```bash
sudo bash deploy/vps_backup.sh --include-docker-images
```

Fresh VPS restore pattern:

```bash
sudo mkdir -p /opt/vps-backups
sudo cp vps-full-YYYYmmdd-HHMMSS.tar.gz /opt/vps-backups/
sudo bash deploy/vps_restore.sh --install-prereqs --restore-root --restore-docker /opt/vps-backups/vps-full-YYYYmmdd-HHMMSS.tar.gz
```

Important: script-based VPS backup is portable recovery, not a byte-for-byte disk image. Hetzner snapshots/backups are still the best complete machine rollback.

### Health Checks

Backend:

```bash
curl http://127.0.0.1:8000/api/health
curl https://quizforge.aabhishek.in/api/health
```

Containers:

```bash
cd /opt/quizforge/quizforge
sudo docker compose ps
sudo docker compose logs -f api worker
```

Open ports:

```bash
ss -tulpn
```

Expected:

- SSH: public 22
- Nginx: public 80/443
- API: `127.0.0.1:8000`
- PostgreSQL and Redis: Docker/internal only

## 13. File And Module Summaries

### Root Files

- `README.md`
  - Project overview, stack, features, local run, provider options, Hetzner deployment, roadmap, and layout.

- `.env.example`
  - Documents required secret and provider environment variables.

- `deploy/update_vps.sh`
  - Interactive VPS deploy helper for the current Nginx production setup.
  - Defaults to `DOMAIN=quizforge.aabhishek.in`, `WEB_ROOT=/var/www/quizforge.aabhishek.in/html`, `REMOTE=origin`, and `BRANCH=main`.
  - Full mode pulls GitHub, rebuilds `api` and `worker`, builds frontend, publishes `frontend/dist` to Nginx root, reloads Nginx, and runs smoke tests.
  - Frontend-only mode pulls GitHub, builds/publishes frontend, reloads Nginx, and runs smoke tests.
  - Backend-only mode pulls GitHub and rebuilds `api` and `worker`.
  - Dry-run prints commands without changing the server.

- `docker-compose.yml`
  - Defines database, Redis, API, worker, and an optional Caddy service for local/alternate containerized serving.
  - VPS production uses Nginx instead of the Compose Caddy service.
  - API publishes `127.0.0.1:8000:8000` so host Nginx can proxy to the container without exposing the API publicly.

- `Caddyfile`
  - Alternative/local Caddy-based HTTPS and reverse proxy config.

- `enhanced prompts.md`
  - Design rationale for moving generation to a two-pass subject-skeleton architecture.
  - Includes prompt templates and warnings against hallucinated links.

- `knowledge_base.md`
  - This consolidated source-of-truth document.

### Backend

- `backend/Dockerfile`
  - Python 3.12 slim image with backend dependencies and Uvicorn command.

- `backend/requirements.txt`
  - FastAPI, SQLAlchemy, Redis/RQ, Anthropic, OpenAI, MarkItDown, PyMuPDF, DOCX/PPTX/EPUB parsing libraries, RapidFuzz.

- `backend/worker.py`
  - Starts an RQ `SimpleWorker` for the `generation` queue.

- `backend/app/config.py`
  - Pydantic settings with provider config, upload unlock code, upload limits, cookie settings, card counts, and model defaults.

- `backend/app/database.py`
  - SQLAlchemy engine and session management.

- `backend/app/main.py`
  - App initialization, CORS, router registration, table creation, lightweight migrations, achievement seeding, first-run invite bootstrap, health endpoint.

- `backend/app/models.py`
  - All persistence models and relationships.

- `backend/app/schemas.py`
  - Request and response schemas.

- `backend/app/security.py`
  - Password hashing, cookie session signing, current user lookup, admin guard.

- `backend/app/routers/auth.py`
  - Invite registration, login, logout, current user summary.

- `backend/app/routers/documents.py`
  - Upload unlock-code validation, file validation, storage, RQ enqueue, Redis-failure fallback, document polling.

- `backend/app/routers/decks.py`
  - Subject CRUD, deck and card CRUD, authorization, user sharing, group sharing, due-card counts, JSON/CSV import and export endpoints.

- `backend/app/routers/demo.py`
  - Public no-login Mental Models demo deck and demo study-session endpoints.

- `backend/app/routers/study.py`
  - Session selection, review submission, XP, streaks, achievements, Smart Review scheduling.

- `backend/app/routers/gamification.py`
  - Leaderboard, achievements, admin invite codes, admin group management.

- `backend/app/services/parsing.py`
  - Converts uploaded documents to Markdown with MarkItDown, splits Markdown into sections, and chunks it for generation.

- `backend/app/services/demo_deck.py`
  - Fixed Mental Models demo deck payload and cards.

- `backend/app/services/deck_io.py`
  - Canonical deck import/export service.
  - Exports decks to `quizforge.deck.v1` JSON and CSV.
  - Imports `.json` and `.csv` deck files.
  - Normalizes difficulty, card type, MCQ options, learning metadata, source refs, and text length.
  - CSV import recognizes `front/back`, `question/answer`, and `term/definition` column pairs.

- `backend/app/services/generation.py`
  - Prompt templates, provider dispatch, JSON parsing repair, subject skeleton cleaning, card cleaning.

- `backend/app/services/tasks.py`
  - End-to-end background generation job.

- `backend/app/services/xp.py`
  - XP math, streak logic, achievement seeding and granting.

- `backend/app/services/fsrs.py`
  - Simplified FSRS-style scheduling.

### Frontend

- `frontend/package.json`
  - React 18, React Router, Vite 5, Tailwind.

- `frontend/Dockerfile`
  - Builds React app in Node image and serves static output with Caddy for the optional local/alternate Compose service.
  - VPS production builds `frontend/dist` and publishes it to the Nginx web root.

- `frontend/vite.config.js`
  - React plugin and dev proxy from `/api` to `localhost:8000`.

- `frontend/tailwind.config.js`
  - Theme tokens, fonts, card shadows, pop and floating-XP animations.

- `frontend/src/lib/api.js`
  - Cookie-aware fetch wrapper with JSON, form upload, and blob download helpers.

- `frontend/src/App.jsx`
  - Auth context, protected routing, public demo routing, nav, theme selector, XP bar.

- `frontend/src/index.css`
  - Theme variables and card styling.

- `frontend/src/pages/Login.jsx`
  - Login/register UI with invite code support and public demo link.

- `frontend/src/pages/Home.jsx`
  - Public logged-out front page with large logo, short app introduction, demo CTA, sign-in link, and sign-up link.

- `frontend/src/pages/Dashboard.jsx`
  - Deck list, due count, empty state, and JSON/CSV deck import button.

- `frontend/src/pages/Upload.jsx`
  - Locked upload gate, drag/drop upload, high-quality toggle, polling.

- `frontend/src/pages/Deck.jsx`
  - Deck detail, study mode selection, JSON/CSV export buttons, card list/editing, admin sharing.
  - In demo mode, reuses the same deck UI against `/api/demo` endpoints and hides write actions.

- `frontend/src/pages/Study.jsx`
  - Flashcard, MCQ, typed-answer, and match study modes.
  - In demo mode, reuses the same study UI against `/api/demo` endpoints and suppresses XP/review writes.

- `frontend/src/pages/Admin.jsx`
  - Invite and group management.

- `frontend/src/pages/Leaderboard.jsx`
  - Weekly XP leaderboard.

- `frontend/src/pages/Achievements.jsx`
  - Badge grid.

### Generated Or Operational Artifacts

- `backend/uploads/*`
  - User-uploaded documents. Treat as data, not source knowledge.

- `backend/quizforge-dev.db`
  - Local development SQLite artifact. Production uses PostgreSQL.

- `output/pdf/quizforge-vps-deployment-guide.pdf`
  - Generated deployment reference PDF.

- `tmp/pdfs/*`
  - PDF generation/rendering scripts and rendered page images used for QA.

## 14. Hidden Insights And Inferred Knowledge

- The strongest learning behavior comes from first-principles generation, not from rote extraction.
- The app's card model is already close to a lightweight knowledge graph because each card can carry first-principle and concept connection metadata.
- Group sharing is intentionally admin-only, even if the deck owner is not the admin.
- Smart Review is opt-in per deck to avoid forcing spaced repetition on all study sessions.
- The current migration approach is lightweight and suited to early development, but Alembic is needed before more schema evolution.
- Document generation is asynchronous because LLM calls can be slow and should not block HTTP requests.
- Frontend polling is simple and robust enough for single-user or friend-group usage.
- Deck import/export deliberately excludes study history and sharing state so files remain portable content packages rather than account backups.
- Raw links were removed from generated cards because LLMs hallucinate URLs and broken links degrade trust.
- The production setup intentionally uses Nginx instead of the repo's Caddy service, so local Docker instructions and production deployment diverge.
- Because production serves frontend assets from Nginx's web root, UI deploys require publishing `frontend/dist` to `/var/www/quizforge.aabhishek.in/html`.
- The project was copied to the server as a nested folder, so deployment docs must always tell operators to verify the directory containing `docker-compose.yml`.
- Passwords used inside `DATABASE_URL` need URL-safe characters or URL encoding.
- `npm audit fix --force` is dangerous in deployment because it can change major frontend tooling versions.

## 15. Reusable Patterns Beyond This Project

### AI Generation

- Use a document-level map before chunk-level generation when outputs need cross-chunk coherence.
- Store structured enrichment separately from concise primary fields.
- Validate model output aggressively and degrade gracefully.
- Ask for fewer high-quality outputs rather than padding to a fixed count.
- Use misconception-driven distractors for better MCQs.
- Prefer search queries or deterministic post-processing over model-generated URLs.

### Learning Systems

- Combine self-grading, objective quizzes, typed recall, and matching to vary cognitive load.
- Award some XP for incorrect attempts to reinforce effort.
- Use append-only XP and review logs for auditability and recomputation.
- Make spaced repetition opt-in when users may want free practice too.
- Represent study progress both as immediate feedback and long-term progress.

### Deployment

- Bind app servers to localhost behind Nginx unless they must be public.
- Use Nginx for static frontend plus `/api/` proxy when the frontend is a SPA.
- Test direct backend health before testing reverse proxy health.
- Check `docker compose ps` port mappings when Nginx returns 502.
- Use `sudo tee` for privileged file writes.
- Avoid shell-special characters in env values consumed by URLs.
- Treat generated deployment guides as living runbooks and update them after real failures.

## 16. Known Gaps And Future Work

- Replace `Base.metadata.create_all` and lightweight migrations with Alembic.
- Add OCR fallback for scanned PDFs.
- Add rate limiting for auth endpoints before opening beyond trusted users.
- Add robust backup restore documentation and test restores.
- Add production monitoring and alerting.
- Add structured logging for generation failures.
- Persist the subject skeleton if future features need concept coverage reports.
- Add embedding-based near-duplicate card detection.
- Add deterministic enrichment for external references if links/search are reintroduced.
- Keep README and deployment docs aligned with the current Nginx production path.
- Consider adding a visible import status/progress message and richer import preview before creating a deck.
- Consider adding Anki-compatible import/export formats if users need broader deck portability.
- Consider replacing simplified FSRS with the `fsrs` package.

## 17. Self-Check

- Source files, backend modules, frontend pages, deployment configs, prompt design notes, and generated deployment artifacts were scanned.
- No GPT-5.2 Prompting Guide PDF was found in the project tree or current attachments; the document applies the requested best-practice style through explicit structure, normalized terminology, runbooks, troubleshooting patterns, and self-checks.
- Sensitive `.env` values, API keys, database passwords, user-uploaded document contents, and local database contents are intentionally excluded.
- The Nginx/Hetzner deployment runbook reflects the actual successful path from this setup session.
- Troubleshooting entries cover the concrete failures encountered: wrong directory, missing Compose file, env variable expansion, Postgres password mismatch, unpublished API port, Node/Vite issues, stale frontend publishing, privileged Nginx writes, and duplicate SSL directives.
- Terminology is normalized around subject skeleton, first principles, core concepts, decks, cards, Smart Review, admin sharing, and group sharing.
- The document is optimized for future human operators and AI agents.
