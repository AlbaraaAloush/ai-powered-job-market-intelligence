# Deployment

How to run the platform locally, in Docker, and in production. The security
pre-deploy checklist lives in [SECURITY.md](SECURITY.md); operational
procedures in [RUNBOOK.md](RUNBOOK.md).

---

## 1. Local development (no Docker)

```bash
# Backend, from RAG/
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --no-server-header

# Frontend, from frontend/
npm install
npm run dev                   # http://localhost:3000 (talks to localhost:8000)
```

Excel is not parsed on every normal backend restart. After adding or changing
a workbook, run this once and commit/package the generated Parquet + manifest:

```bash
cd RAG
python build_runtime_data.py
```

With `COMPACT_RUNTIME_DATA=true` (the default), startup validates the source
fingerprint and loads `data/runtime_compact.parquet`. It falls back to Excel
only when that artifact is missing or stale.

The backend exposes dashboard routes after loading the compact tabular data. It
connects to Qdrant in a background thread, while the embedding model is loaded
only by the first genuinely semantic question. `/health` reports the current
capability:

| `rag_status` | Behavior |
|---|---|
| `ready` | SQL, Pandas, and Qdrant semantic retrieval are available |
| `degraded` | Qdrant failed; chat still uses SQL/Pandas grounding |
| `disabled` | `ENABLE_RAG=false`; dashboard and exports only |
| `unavailable` | Both semantic and structured chat initialization failed |

The dashboard does not read Qdrant. A deleted vector cluster cannot block
`/api/datasets`, `/api/dashboard`, drill-down, or exports.

On the target Windows laptop, the measured behavior is:

- core API and deterministic chat ready in about 3 seconds;
- deterministic answers around 2–4 seconds end to end;
- first semantic question up to 40 seconds while the local embedding model
  loads, then roughly 9–22 seconds for subsequent semantic questions.

## 2. Docker (development stack)

```bash
cp RAG/.env.example RAG/.env  # fill in keys
docker compose up --build     # backend :8000, frontend :3000
```

The frontend image bakes `NEXT_PUBLIC_API_URL=http://localhost:8000` so the
browser calls the backend directly. Both containers have healthchecks; the
frontend waits for the backend to be healthy.

## 3. Docker (production stack)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Topology — nginx is the only published port (80):

```
                    ┌─────────────────────── docker network ───────────────────────┐
Internet ──:80──▶ nginx ──▶ /            ──▶ frontend:3000  (Next.js standalone)   │
                    │  ──▶ /api/*, /health ──▶ backend:8000 (uvicorn, internal)    │
                    │  ──▶ /metrics  ──▶ 404 (scraped internally, never public)    │
                    └───────────────────────────────────────────────────────────────┘
```

Required in `RAG/.env` for production:

| Variable | Production value |
|---|---|
| `ENVIRONMENT` | `production` |
| `APP_VERSION` | your release tag (shown on `/health` and in Sentry) |
| `ALLOWED_ORIGINS` | the public origin, e.g. `https://jobs.example.org` — **not** localhost |
| `ENABLE_RAG` | `true` for chat, `false` for a dashboard-only service |
| `REQUIRE_RAG` | `true` only when missing RAG credentials must stop deployment |
| `QDRANT_URL`, `QDRANT_API_KEY` | optional for structured chat; required for semantic retrieval |
| `FANAR_API_KEY` and/or `OPENAI_API_KEY` | required for chat |
| `SENTRY_DSN` *(optional)* | enables error tracking (see OBSERVABILITY.md) |
| `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` *(optional)* | enables LLM tracing |
| `DATABASE_URL` | optional managed PostgreSQL URL for durable feedback and chat sessions |
| `REQUIRE_DATABASE` | `false` for the diploma/demo deployment; `true` only when durable application records are mandatory |

### Durable application storage

Qdrant stores embeddings and job payloads for retrieval; it is not the
application database. The dashboard reads the versioned source snapshots
packaged with the backend. Feedback and chat sessions use PostgreSQL whenever
`DATABASE_URL` is set. Without that variable, feedback uses local SQLite and
sessions stay in memory. On an ephemeral container host those local records can
be lost during a restart or redeploy; configured Langfuse feedback remains in
Langfuse.

Create a managed PostgreSQL database, require TLS in its connection URL, then run:

```bash
cd RAG
python migrate_database.py
```

The migration is idempotent and also copies records from the legacy
`chroma_db/feedback.sqlite3` file when present. Set `REQUIRE_DATABASE=true` if
a later production deployment must refuse to start without durable storage.
Never put the connection URL in Git; configure it as a hosting-platform secret.

For the public diploma deployment, Supabase is the recommended managed
PostgreSQL provider. Create a project, open **Connect**, copy the **Session
pooler** connection string (port 5432), add `sslmode=require`, and set that full
value as `DATABASE_URL` on the Python backend host. Also set
`REQUIRE_DATABASE=true`. The frontend does not need a Supabase URL, anon key,
or database password because all database access goes through FastAPI.

The application creates its tables idempotently at startup. They store:

- anonymous two-hour chat sessions and their last 20 messages;
- explicit helpful/not-helpful feedback, reason, and optional comment;
- private operational usage events (request count, language, response mode,
  latency, success, selected-dataset count), without IP addresses or raw
  question text.

Usage events are for the project owner/research evaluation, not a public user
history feature. No public endpoint exposes them.

For local Docker development, `docker-compose.yml` includes PostgreSQL with a
named volume. The production Compose file expects an external managed service
and deliberately does not run a database container.

The frontend image is built with `NEXT_PUBLIC_API_URL=""` → same-origin
relative URLs; every request flows through nginx.

### Image sizes

The backend Dockerfile supports two builds:

```bash
# Lightweight API: dashboard plus SQL/Pandas chat fallback
docker build --build-arg INSTALL_RAG_MODELS=false -t mihna-api-lite ./RAG

# Full semantic RAG: CPU torch plus the multilingual embedding model
docker build --build-arg INSTALL_RAG_MODELS=true -t mihna-api-full ./RAG
```

Set the same option for Compose with `INSTALL_RAG_MODELS=false` or `true`.
The lightweight build avoids the large Torch/model layers that often exceed
free hosting build and image limits. Set `COMPACT_RUNTIME_DATA=true` on a
memory-constrained host; the loader keeps derived bilingual signals and drops
large raw page-text columns that the dashboard does not display.

Measured locally, the compact backend uses about 298 MB RSS before semantic
use and about 555 MB after loading the embedding model (with hybrid reranking
off). A 1 GB host is therefore possible but leaves little room for Python,
request spikes, and platform overhead; 2 GB RAM is the safe full-RAG target.
Dashboard-only or deterministic-chat deployments can use the lightweight image.

## 4. Split deployment (recommended for Vercel)

Deploy `frontend/` as its own Vercel project and set its project Root Directory
to `frontend`. Add this production environment variable:

```text
NEXT_PUBLIC_API_URL=https://your-python-backend.example
```

Deploy the Python API on a container host. Set `ALLOWED_ORIGINS` to the exact
Vercel production URL. Do not deploy the Python API, Excel files, Torch, or the
embedding model as Vercel Functions.

### TLS

Not configured in-repo (host-specific). Two options:
1. **Platform TLS** (Railway/Render/Fly/a cloud LB): terminate there, keep
   nginx on port 80 behind it. `--proxy-headers` is already set on uvicorn.
2. **Self-managed**: add a 443 server block + certs to `nginx/nginx.conf`
   (marked with a TODO) and publish 443 in the prod compose.

HSTS headers are already emitted by both apps and activate the moment TLS is live.

## 5. Environment separation

| | development | production |
|---|---|---|
| config validation | warns and continues | **fails to boot** on problems |
| `ALLOWED_ORIGINS` | localhost:3000 | public origin only (localhost rejected) |
| ports | backend+frontend published | nginx only |
| compose file | `docker-compose.yml` | `docker-compose.prod.yml` |

## 6. Data & index lifecycle

- Source workbooks and the generated compact Parquet snapshot are baked into
  the backend image. Production startup reads Parquet, not Excel.
- Vectors live in **Qdrant Cloud** — not in the image, not in a volume. The
  manifest (`chroma_db/_manifest.json`, hash of source files) is baked in so a
  fresh container recognises the index is already built and skips re-embedding.
- Adding a new data dump = drop the file in `RAG/data/`, run
  `python build_runtime_data.py`, then `python build_index.py` once
  (incremental — embeds only the new file), and rebuild the backend image.

## 7. Backup & recovery

- **Source data**: the `.xlsx` files in git are the source of truth.
- **Vectors**: recoverable from source data at any time via `build_index.py`
  (full rebuild ≈ embedding 30k rows). Qdrant Cloud's own snapshots are the
  faster path — enable them in the cluster settings.
  If a full upload is interrupted, run `python build_index.py --resume` to
  skip deterministic point IDs already accepted by Qdrant and continue only
  the missing embeddings.
- **Sessions**: in-memory by design (2 h TTL); lost on restart. Acceptable for
  a stateless public assistant — nothing durable lives in the backend process.
- **Rollback**: images are immutable; keep the previous tag and
  `docker compose -f docker-compose.prod.yml up -d` with it.

## 8. Scaling notes (read before adding replicas)

Two things are per-process today and must move to shared stores before
horizontal scaling:
1. **Rate limits** (SlowAPI, in-memory) — effective limit multiplies by
   replica count. Move to Redis-backed storage.
2. **Sessions** (in-memory dict) — a second replica won't see the first's
   chat history. Move to Redis, or pin sessions to a replica (sticky LB).

Single-replica vertical scaling has no such constraints; the app is CPU-bound
on embedding (per chat request) and pandas (mitigated by the dashboard cache).
