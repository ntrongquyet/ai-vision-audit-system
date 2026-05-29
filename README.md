# AI Vision Audit System

AI-powered cross-checking of building-site photos against a written Scope of Works (SoW),
plus semantic Q&A over a project's photo album.

---

## 1. Overview

The AI Vision Audit System ingests the photos taken on a building/renovation site and the
text of the project's **Scope of Works**, then uses AI to produce a structured audit report
containing three kinds of findings:

- **Discrepancies** — things visible in the photos that the SoW does not account for (e.g. rust
  on a roof that the scope never mentions painting/treating).
- **Ambiguity alerts** — vague or risky phrasing in the SoW that should be tightened before the
  job is priced or signed off, with a recommended rewording.
- **Safety-equipment recommendations** — gear the job will need given what the photos show
  (e.g. scaffolding / boom lift for high walls, lead-paint precautions, etc.).

On top of the audit, the system supports **semantic chat** over the photo album: a user can ask a
natural-language question ("Is there any visible water damage?") and get an answer grounded only
in the photos that are semantically most relevant, together with the reference image URLs.

### "Process Once, Query Anywhere"

Vision analysis and embedding are expensive, so they are done **once** per image, at indexing
time. Each photo is described by a vision model, the description is embedded into a vector, and the
tags / description / embedding are persisted in Postgres (pgvector). Every later operation — the
audit and every chat question — runs against this pre-computed index. No image is re-analysed on
the audit or chat path; the audit aggregates stored descriptions and chat does a vector top-K
lookup.

### Stack

- **API**: FastAPI (async)
- **Storage / vectors**: Postgres + the `pgvector` extension (HNSW index) — Supabase-ready
- **AI**: a single OpenAI-compatible client pointed at a **9router** gateway. One gateway, three
  roles (vision / reasoning / embedding), each selected by an environment variable.

---

## 2. Architecture

Three flows, all sharing the pre-computed visual index.

**Indexing** (`POST /api/v1/projects/index`)
1. A row is inserted into the `project_index_jobs` table (status `pending`) and the request
   returns immediately with `202 Accepted` and a `job_id`.
2. A FastAPI **BackgroundTask** processes the image URLs in batches (default 5 at a time,
   `AI_BATCH_SIZE`), with at most `AI_MAX_CONCURRENCY` (default 5) concurrent AI calls guarded by
   an `asyncio.Semaphore`.
3. For each image: vision model → `tags` + `detailed_description` → embedding → row in
   `project_visual_indices`. Per-image failures are isolated (logged, counted as failed) so one
   bad URL does not sink the whole job.
4. The job row is finalized to `completed`, `partial`, or `failed`, with succeeded/failed counts.
   Clients poll `GET /{project_id}/status`.

**Audit** (`POST /api/v1/projects/audit`)
1. Guard: if the project has no indexed images yet, return `422` (you must index first).
2. Aggregate all stored `detailed_description`s for the project into a single context block.
3. Send context + SoW to the **reasoning** model with a JSON-object response format; the result is
   validated against `AuditReportSchema` (with one repair retry if the JSON is malformed).
4. The report is persisted to `project_audit_reports` and returned.

**Chat** (`POST /api/v1/projects/chat`)
1. Embed the question.
2. pgvector **top-K** similarity search (`match_visual_indices` SQL function, cosine similarity,
   `MATCH_THRESHOLD` / `MATCH_COUNT`) scoped to the project.
3. Feed the matched descriptions to the reasoning model and return a concise answer plus the
   reference image URLs. If nothing clears the threshold, a "no relevant photos" answer is returned
   without calling the model.

**AI access.** All AI is reached through one `AsyncOpenAI` client whose `base_url` is the
configurable 9router gateway (`AI_BASE_URL`). The model used per role is an env var
(`VISION_MODEL`, `REASONING_MODEL`, `EMBEDDING_MODEL`), so models can be swapped without code
changes. Every AI call is wrapped with a Tenacity retry (3 attempts, exponential backoff).

---

## 3. Prerequisites

- **Python 3.12** — on Windows, use the launcher: `py -3.12`. (The project requires `>=3.11`;
  3.12 is recommended.)
- **Docker Desktop** — for the local Postgres/pgvector database (and the optional Adminer UI).
- **A 9router (OpenAI-compatible) gateway** — you need its base URL and an API key, and the names
  of a vision model, a reasoning model, and an embedding model exposed by that gateway.

---

## 4. Local setup (Windows PowerShell)

All commands are run from the repo root (`d:\demo\ai-vision-audit-system`).

```powershell
# 1. Create the virtual environment
py -3.12 -m venv .venv

# 2. Install the package (editable) with dev/test extras
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 3. Create your .env from the template, then edit it
Copy-Item .env.example .env
#    Fill in real values: AI_BASE_URL, AI_API_KEY, VISION_MODEL, REASONING_MODEL,
#    EMBEDDING_MODEL, and a strong APP_API_KEY.

# 4. Start the Postgres/pgvector database
docker compose up -d db

# 5. Apply the SQL migrations (creates extension, tables, indexes, match function)
.\.venv\Scripts\python.exe scripts/apply_migrations.py

# 6. Run the API server
.\.venv\Scripts\uvicorn.exe app.main:app --reload --timeout-keep-alive 90
```

- Demo UI: <http://localhost:8000>
- Interactive OpenAPI docs: <http://localhost:8000/docs>
- Adminer (optional DB browser, if you `docker compose up -d adminer`): <http://localhost:8080>

> **Why `--timeout-keep-alive 90`? (EX-03)** A deep audit runs a large reasoning request over the
> aggregated photo descriptions and can take **30–45 seconds**. The default Uvicorn keep-alive
> timeout would drop such connections, so the server (and the `Dockerfile`) raise it to 90s. Any
> client calling `/audit` should likewise allow a 90s+ request timeout.

---

## 5. Environment variables

Every variable in `.env.example`:

| Variable | Meaning | Default |
| --- | --- | --- |
| `AI_BASE_URL` | Base URL of the OpenAI-compatible 9router gateway. **Required.** | `https://9router.example/v1` |
| `AI_API_KEY` | API key for the 9router gateway. **Required.** | `replace-me` |
| `VISION_MODEL` | Model used to describe/tag each image at indexing time. | `gemini-2.0-flash` |
| `REASONING_MODEL` | Model used for the audit and for chat answers. | `claude-3-5-sonnet` |
| `EMBEDDING_MODEL` | Model used to embed descriptions and chat questions. | `text-embedding-3-small` |
| `EMBEDDING_DIM` | Output dimension of the embedding model. **Must match** the `vector(N)` in the migrations. | `1536` |
| `AI_MAX_CONCURRENCY` | Max concurrent AI calls during indexing (semaphore). | `5` |
| `AI_BATCH_SIZE` | Number of images processed per batch during indexing. | `5` |
| `APP_API_KEY` | Shared secret expected in the `X-API-KEY` header on every protected endpoint. **Required.** | `dev-secret-key` |
| `DATABASE_URL` | SQLAlchemy async Postgres URL (`postgresql+asyncpg://...`). **Required.** | `postgresql+asyncpg://postgres:postgres@localhost:5432/audit` |
| `UPLOAD_DIR` | Local directory for the dev-only `/uploads` endpoint and `/files` static mount. | `uploads` |
| `UPLOAD_PUBLIC_BASE_URL` | Public base URL prefix returned for files saved via dev `/uploads`. | `http://localhost:8000/files` |
| `MATCH_THRESHOLD` | Minimum cosine similarity for a photo to be returned by chat search. | `0.7` |
| `MATCH_COUNT` | Max number of photos returned by the chat top-K search. | `3` |

> **`EMBEDDING_DIM` note.** The migrations declare `vector(1536)` and the `match_visual_indices`
> function takes a `vector(1536)`. If you switch to an embedding model with a different output
> dimension, you must set `EMBEDDING_DIM` to that value **and** change the `vector(N)` in
> `migrations/001_init.sql` and `migrations/002_match_function.sql` to match — otherwise inserts
> and searches will fail.

---

## 6. Running tests

```powershell
# Unit tests only (no database needed)
.\.venv\Scripts\python.exe -m pytest -m "not integration"

# Integration tests (require Docker DB up + migrations applied)
.\.venv\Scripts\python.exe -m pytest -m integration
```

Integration tests are marked with the `integration` marker (defined in `pyproject.toml`) and need
a running Postgres with migrations applied — start it exactly as in the Local setup steps 4–5
before running them.

### Mosgiel acceptance test

End-to-end acceptance against the bundled Mosgiel sample photos. It uploads ~30 images, indexes
them, polls until the job finishes, runs an audit with a **deliberately incomplete** SoW, and
asserts the AI detects ≥ 90% of the planted issues (rust, mould/moss, pressure-washing,
scaffolding/ladder/boom, lead paint).

1. Start the server with **real** AI credentials (the audit calls the live gateway):
   ```powershell
   .\.venv\Scripts\uvicorn.exe app.main:app --timeout-keep-alive 90
   ```
2. In another terminal, run the script:
   ```powershell
   .\.venv\Scripts\python.exe scripts/run_mosgiel_stress_test.py
   ```

The script honours `API_URL` (default `http://localhost:8000`) and `APP_API_KEY` (default
`dev-secret-key`) environment variables.

---

## 7. API reference

All endpoints under `/api/v1/...` require the header **`X-API-KEY: <APP_API_KEY>`**. A missing or
wrong key returns **`401`**. `GET /health` is unauthenticated.

### `POST /api/v1/projects/index`

Start indexing a project's images in the background.

- **Auth:** `X-API-KEY`
- **Request:**
  ```json
  { "project_id": "PROJ-3132", "image_urls": ["https://.../a.jpg", "https://.../b.jpg"] }
  ```
- **Response — `202 Accepted`:**
  ```json
  {
    "status": "success",
    "message": "Bulk image indexing initiated in background.",
    "project_id": "PROJ-3132",
    "job_id": "f1b9...uuid",
    "total_images": 2
  }
  ```
- **Status codes:** `202` accepted · `422` if `image_urls` is empty (Pydantic validation) ·
  `401` bad/missing key.

```bash
curl -X POST http://localhost:8000/api/v1/projects/index \
  -H "X-API-KEY: dev-secret-key" -H "Content-Type: application/json" \
  -d '{"project_id":"PROJ-3132","image_urls":["https://example.com/a.jpg"]}'
```

### `GET /api/v1/projects/{project_id}/status`

Poll the latest indexing job for a project.

- **Auth:** `X-API-KEY`
- **Response — `200 OK`:**
  ```json
  {
    "project_id": "PROJ-3132",
    "job_id": "f1b9...uuid",
    "status": "completed",
    "total_images": 30,
    "processed_images": 30,
    "succeeded_images": 29,
    "failed_images": 1
  }
  ```
  `status` is one of `pending`, `processing`, `completed`, `partial`, `failed`.
- **Status codes:** `200` · `404` if the project has no indexing job · `401` bad/missing key.

```bash
curl http://localhost:8000/api/v1/projects/PROJ-3132/status \
  -H "X-API-KEY: dev-secret-key"
```

### `POST /api/v1/projects/audit`

Cross-check the indexed photos against a Scope of Works and return a structured report.

- **Auth:** `X-API-KEY`
- **Request:**
  ```json
  { "project_id": "PROJ-3132", "scope_text": "Interior and exterior repaint. Paint all timber weatherboard walls and window frames." }
  ```
- **Response — `200 OK`:**
  ```json
  {
    "project_id": "PROJ-3132",
    "status": "completed",
    "audit_report": {
      "discrepancies": [
        {
          "issue_title": "Visible roof rust not in scope",
          "evidence_description": "Photo shows significant rust on the corrugated roof sheets.",
          "suggested_action": "Add rust treatment and priming to the scope before painting.",
          "related_image_url": "https://example.com/roof.jpg"
        }
      ],
      "ambiguity_alerts": [
        {
          "original_text": "Clean surfaces before application.",
          "risk_analysis": "Does not specify the cleaning method, leaving pricing open.",
          "recommended_phrasing": "Pressure-wash all surfaces at 2000 psi to remove mould and moss before painting."
        }
      ],
      "safety_equipment_recommendations": [
        { "equipment_name": "Scaffolding", "reason": "High exterior walls require working at height." }
      ]
    }
  }
  ```
- **Status codes:** `200` · `422` if the project has not been indexed yet (index first) ·
  `401` bad/missing key. (See the note in §8 about `503` when the AI gateway is overloaded.)
- **Timeout:** allow ≥ 90s; deep audits take 30–45s.

```bash
curl -X POST http://localhost:8000/api/v1/projects/audit \
  -H "X-API-KEY: dev-secret-key" -H "Content-Type: application/json" \
  -d '{"project_id":"PROJ-3132","scope_text":"Interior and exterior repaint of timber weatherboards."}'
```

### `POST /api/v1/projects/chat`

Ask a natural-language question answered only from the project's most relevant photos.

- **Auth:** `X-API-KEY`
- **Request:**
  ```json
  { "project_id": "PROJ-3132", "user_question": "Is there any visible water damage?" }
  ```
- **Response — `200 OK`:**
  ```json
  {
    "answer_text": "Yes — two photos show staining and swollen timber near the eaves, consistent with water ingress.",
    "reference_image_urls": ["https://example.com/eaves1.jpg", "https://example.com/eaves2.jpg"]
  }
  ```
  If no photo clears `MATCH_THRESHOLD`, `answer_text` is `"No relevant photos found for this
  question."` and `reference_image_urls` is `[]`.
- **Status codes:** `200` · `401` bad/missing key.

```bash
curl -X POST http://localhost:8000/api/v1/projects/chat \
  -H "X-API-KEY: dev-secret-key" -H "Content-Type: application/json" \
  -d '{"project_id":"PROJ-3132","user_question":"Is there any visible water damage?"}'
```

### `POST /api/v1/uploads` (dev only)

Save uploaded files to local disk and return their public URLs. Intended only for local testing —
**not used in production** (Bubble uploads directly to Supabase Storage; see §8).

- **Auth:** `X-API-KEY`
- **Request:** `multipart/form-data` with one or more `files` fields.
- **Response — `200 OK`:**
  ```json
  { "image_urls": ["http://localhost:8000/files/ab12_a.jpg", "http://localhost:8000/files/cd34_b.jpg"] }
  ```
- **Status codes:** `200` · `401` bad/missing key.

### `GET /health`

Unauthenticated liveness check.

- **Response — `200 OK`:** `{ "status": "ok" }`

---

## 8. Bubble.io integration guide

### API Connector setup

In Bubble's **API Connector** plugin, create a new API with:

- **Base URL** = your deployed API origin (e.g. `https://your-api.example.com`).
- A shared header on every call: **`X-API-KEY`** = your `APP_API_KEY`.
- `Content-Type: application/json` for the JSON endpoints.

### End-to-end flow

1. **Upload + index.** Bubble uploads the site photos to **Supabase Storage** and collects the
   resulting public URLs. Then call `POST /api/v1/projects/index` with
   `{ project_id, image_urls }`. The call returns `202` immediately with a `job_id`.
2. **Poll status.** Call `GET /api/v1/projects/{project_id}/status` on a timer until `status` is
   `completed`, `partial`, or `failed`. (`partial` = some images failed but the index is usable;
   `failed` = nothing indexed.)
3. **Audit.** Call `POST /api/v1/projects/audit` with `{ project_id, scope_text }`. **Set this
   Bubble API call's timeout to ≥ 90 seconds** — deep audits take 30–45s.
4. **Chat.** Call `POST /api/v1/projects/chat` with `{ project_id, user_question }` to power a
   Q&A box over the album.

### Error handling in Bubble

- **`422` on audit** → the project's images are not indexed yet. Make sure step 1–2 completed
  (status `completed`/`partial`) before calling audit; surface a "please index photos first"
  message.
- **`422` on index** → `image_urls` was empty; don't send the call with an empty list.
- **`401`** → the `X-API-KEY` header is missing or wrong.
- **`503`** → the AI gateway was overloaded (the audit/chat AI call exhausted its retries). Show a
  friendly *"The system is busy processing — please try again in a minute."* and let the user
  retry.

### Production note

In production, Bubble uploads photos to **Supabase Storage directly** and passes those public URLs
to `/index`. The dev-only `POST /api/v1/uploads` endpoint is **not** used in production.

---

## 9. Deploy to Supabase cloud

1. **Run the migrations** in order in the Supabase **SQL Editor** (or via the Supabase CLI):
   - `migrations/001_init.sql` — enables the `vector` extension, creates the
     `project_visual_indices`, `project_audit_reports`, and `project_index_jobs` tables, and
     creates the **HNSW** cosine index on the embedding column.
   - `migrations/002_match_function.sql` — creates the `match_visual_indices(...)` similarity
     function used by chat.
2. **Point the app at Supabase.** Set `DATABASE_URL` to the Supabase Postgres connection string in
   the SQLAlchemy async form:
   ```
   postgresql+asyncpg://postgres:<password>@<host>:5432/postgres
   ```
   (The `+asyncpg` driver is required — the app uses SQLAlchemy async.)
3. **Deploy the API.** Build and run the provided `Dockerfile` (or any host that can run the
   FastAPI app). Keep the **90s** keep-alive timeout — the container CMD already passes
   `--timeout-keep-alive 90`. Set all required env vars (`AI_BASE_URL`, `AI_API_KEY`, the model
   names, `APP_API_KEY`, `DATABASE_URL`).
4. **Data sovereignty (BR-05).** All vectors, tags, descriptions, jobs and audit reports live in
   the client's **own Supabase** project. No project data is stored outside the client's database.

> **`EMBEDDING_DIM` must match the migration's `vector(N)`** (default 1536) and your embedding
> model's real output dimension — see §5.

---

## 10. Project structure

```
ai-vision-audit-system/
├─ app/
│  ├─ main.py              # FastAPI app: routers, /health, /files + UI static mounts
│  ├─ config.py            # Pydantic settings loaded from .env
│  ├─ security.py          # X-API-KEY dependency (401 on mismatch)
│  ├─ api/                 # HTTP routers
│  │  ├─ routes_index.py   #   POST /api/v1/projects/index   (202, BackgroundTask)
│  │  ├─ routes_status.py  #   GET  /api/v1/projects/{id}/status
│  │  ├─ routes_audit.py   #   POST /api/v1/projects/audit
│  │  ├─ routes_chat.py    #   POST /api/v1/projects/chat
│  │  └─ routes_uploads.py #   POST /api/v1/uploads  (dev only)
│  ├─ core/                # AI access layer
│  │  ├─ ai_client.py      #   single AsyncOpenAI client → 9router base_url
│  │  ├─ resilience.py     #   Tenacity retry + concurrency semaphore
│  │  ├─ prompts.py        #   system prompts
│  │  ├─ vision.py         #   image → tags + description
│  │  ├─ embeddings.py     #   text → embedding vector
│  │  └─ reasoning.py      #   audit report generation (JSON-validated)
│  ├─ db/                  # SQLAlchemy async engine, ORM models, repositories
│  ├─ models/schemas.py    # Pydantic request/response + AI output schemas
│  ├─ services/            # job / indexing / audit / chat orchestration
│  └─ static/              # demo UI (served at /)
├─ migrations/             # 001_init.sql, 002_match_function.sql
├─ scripts/                # apply_migrations.py, run_mosgiel_stress_test.py
├─ tests/                  # unit + integration tests (pytest)
├─ docs/                   # spec, design, sample data
├─ uploads/                # local file store for dev /uploads
├─ docker-compose.yml      # local Postgres/pgvector + Adminer
├─ Dockerfile              # production API image (90s keep-alive)
├─ pyproject.toml
└─ .env.example
```

---

## 11. Known limitations / notes

- **Empty `image_urls` returns `422`, not `400`.** The FRS specified `400` for an empty image list,
  but validation is enforced by a Pydantic `field_validator`, so FastAPI returns `422 Unprocessable
  Entity`. Behaviour is correct (the request is rejected); only the status code differs from the
  original FRS wording.
- **`503` is the intended overload response (EX-01).** When an audit/chat AI call exhausts its 3
  retries because the gateway is overloaded, the design calls for a `503` with a friendly
  "try again in a minute" message. The current build wraps AI calls in retries but does not yet
  install a global handler that maps the final failure to `503` — until that handler is added, an
  exhausted retry surfaces as a `500`. Bubble should treat both `500` and `503` from audit/chat as
  "AI busy, retry shortly".
- **BackgroundTasks is in-process.** Indexing runs inside the API process via FastAPI
  `BackgroundTasks`; jobs do not survive a process restart and do not scale across workers. The
  design spec notes a future migration to a durable queue (e.g. Redis/RQ).
- **The demo UI is unhardened.** The static UI under `app/static` (served at `/`) is for local
  testing/demo only and is not production-hardened.
```
