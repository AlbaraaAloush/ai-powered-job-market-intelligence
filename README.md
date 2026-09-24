# Mihna: AI-Powered Job Market Intelligence

> Built at **HBKU (Hamad Bin Khalifa University)** · Data sources: **Bayt.com + LinkedIn** · QCRI Internship 2026

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant_Cloud-red)](https://qdrant.tech)
[![Fanar](https://img.shields.io/badge/LLM-Fanar%20%7C%20OpenAI-purple)](https://api.fanar.qa)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black)](https://nextjs.org)

Mihna is a research platform for exploring job-market data across **Qatar, Saudi Arabia, and the UAE**. It combines data preparation, interactive dashboards, country and period comparisons, and optional **English/Arabic question answering** over job postings from **Bayt.com and LinkedIn**.

- **Explore advertised demand:** analyze job categories, skills, salaries, experience, career levels, education, employment types, and other posting attributes.
- **Compare and inspect:** filter by country, period, and source; drill into supporting postings; export results as CSV or JSON.
- **Ask the data:** combine structured analytics and retrieval-augmented generation (RAG) for questions grounded in the selected datasets.

The bundled snapshot contains **55,616 posting records across 11 source-country-period datasets**. Records from different periods may overlap; this is not a count of unique vacancies across all dates.

## Runtime flow

The dashboard and RAG use the same source data but are operationally independent:

```text
Excel/CSV snapshots
  -> one-time normalization by RAG/build_static_dashboard.py
  -> versioned static JSON in frontend/public/data/dashboard
  -> Vercel/CDN delivery + browser-side filters, charts, drill-down, CSV/JSON export

Chat (optional, independent)
  -> structured analytics + Qdrant vectors
  -> Fanar/OpenAI answer generation
```

The dashboard does not start Python, parse Excel, require Docker, or wait for
Qdrant. The optional local RAG backend can still be started separately.

---

## Quick Start

### Dashboard only (Node.js 20.9+ and npm)

```sh
git clone https://github.com/AlbaraaAloush/ai-powered-job-market-intelligence.git
cd ai-powered-job-market-intelligence
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open **http://localhost:3000** for the landing page or **http://localhost:3000/app** for the dashboard. The committed dashboard data requires no Python backend or API keys. Chat is disabled by default.

### Optional full app setup (Windows / PowerShell)

```powershell
git clone https://github.com/AlbaraaAloush/ai-powered-job-market-intelligence.git
cd ai-powered-job-market-intelligence
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r RAG\requirements.txt -r RAG\requirements-dev.txt
npm --prefix frontend ci
Copy-Item RAG\.env.example RAG\.env
```

Add the required API credentials to `RAG/.env`. Never commit that file. For the
full local chat, create `frontend/.env.local` with:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
ENABLE_CHAT=true
```

### Run

```powershell
# Fast dashboard only (no Docker, database, Python, or API keys)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1

# Complete local app: dashboard + API + RAG + feedback storage
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1 -WithRag
```

Open **http://localhost:3000/app** for the dashboard or **http://localhost:3000/app/chat** for the RAG chat.

Only after the source Excel/CSV files change, rebuild and commit the static
snapshot:

```powershell
.\scripts\build-dashboard-data.ps1
```

On the first full start, loading the local embedding model can take roughly one
minute. The script waits until `/health` reports `rag_status: ready`; it does not
reprocess Excel. Later starts reuse the prebuilt compact data and Qdrant index.

Feedback and anonymous usage events persist to local SQLite by default. Set
`DATABASE_URL` to a Supabase/Postgres connection string if the team also needs
persistent chat sessions across backend restarts. No account, IP address, or raw
question text is stored in usage events.

Run the local test suite with:

```powershell
.\scripts\test-local.ps1 -IncludeRag
```

Live LLM evaluation (uses API quota):

```powershell
.\scripts\test-local.ps1 -IncludeLiveRag
```

The live evaluation covers 52 English and Arabic scenarios: exact analytics,
comparisons, trends, skills, salaries, follow-ups, semantic retrieval,
abstention, prompt injection, and safety refusals.

See [RAG/README.md](RAG/README.md) for full backend setup.

### Vercel showcase

Set the Vercel project root to `frontend`. Leave `ENABLE_CHAT` unset (or set it
to `false`). Vercel then serves the interactive dashboard from committed JSON;
the Chat navigation is hidden and `/app/chat` returns 404. This showcase needs
no Python backend, database, Qdrant, Docker, or AI API key.

---

## Documentation

| Document | Covers |
|---|---|
| [PRODUCTION_RAG.md](PRODUCTION_RAG.md) | Tracing, grounding, evaluation, feedback, and ingestion controls |
| [PROJECT_SPEC.md](PROJECT_SPEC.md) | Living spec + full sprint history (what shipped, when, why) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system fits together: request/RAG/filter/SQL/Qdrant flows |
| [API.md](API.md) | Every HTTP endpoint, request/response shapes, validation rules |
| [SECURITY.md](SECURITY.md) | Threat model, implemented controls, pre-deploy checklist |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Local / Docker / production (nginx) deployment |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Prometheus metrics, Sentry/Langfuse activation |
| [RUNBOOK.md](RUNBOOK.md) | Operational procedures (restart, reindex, incident response) |

---

## Known Limitations

1. **Salary data is sparse**: salary statistics cover only postings that disclose salary, not all jobs.
2. **Data is a snapshot**: postings scraped at specific dates. Job market changes daily.
3. **Source coverage**: covers Bayt.com and LinkedIn only, not the full GCC market.
4. **Arabic bilingual enrichment**: requires the corresponding `_AR_` file to be present for each Bayt EN file. LinkedIn has no Arabic portal equivalent.

---

## Team

The team contributors are:

| Role | Contributor |
|---|---|
| RAG System, Pipeline, UI, Evaluation | Mohammad Faiz Jabir |
| Data Collection & Preprocessing | Albaraa Aloush |
| Front-End | Yahya Taha |
| Supervision | Dr. Hamdy Mubarak |
| Contributor | Ummar Abbas |

**Institution:** Hamad Bin Khalifa University (HBKU): QCRI Summer Internship 2026
