# GCC Job Market Intelligence System
### RAG-Powered Labor Market Analytics Chatbot

See [PRODUCTION_RAG.md](PRODUCTION_RAG.md) for tracing, grounding, evaluation, feedback, and ingestion controls.

> Built at **HBKU (Hamad Bin Khalifa University)** · Data sources: **Bayt.com + LinkedIn** · QCRI Internship 2026

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant_Cloud-red)](https://qdrant.tech)
[![Fanar](https://img.shields.io/badge/LLM-Fanar%20%7C%20OpenAI-purple)](https://api.fanar.qa)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-black)](https://nextjs.org)

A conversational AI assistant that answers natural-language questions about the Gulf job market using **55,616 job postings from Bayt.com and LinkedIn** across Qatar, Saudi Arabia, and the UAE — in both **English and Arabic**.

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

### First-time setup (Windows / PowerShell)

```powershell
git clone https://github.com/mhdfaizjabir/jobmarket_bot.git
cd jobmarket_bot
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

Run the verified local test suite with:

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
| [PROJECT_SPEC.md](PROJECT_SPEC.md) | Living spec + full sprint history (what shipped, when, why) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system fits together — request/RAG/filter/SQL/Qdrant flows |
| [API.md](API.md) | Every HTTP endpoint, request/response shapes, validation rules |
| [SECURITY.md](SECURITY.md) | Threat model, implemented controls, pre-deploy checklist |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Local / Docker / production (nginx) deployment |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Prometheus metrics, Sentry/Langfuse activation |
| [RUNBOOK.md](RUNBOOK.md) | Operational procedures (restart, reindex, incident response) |

---

## Known Limitations

1. **Salary data is sparse** — only ~7% of postings disclose salary. All salary stats are based on this subset.
2. **Data is a snapshot** — postings scraped at specific dates. Job market changes daily.
3. **Source coverage** — covers Bayt.com and LinkedIn only, not the full GCC market.
4. **Arabic bilingual enrichment** — requires the corresponding `_AR_` file to be present for each Bayt EN file. LinkedIn has no Arabic portal equivalent.

---

## Research Foundation

| Paper | Contribution |
|---|---|
| **HyST (2025)** — Hybrid Retrieval over Semi-Structured Tabular Data | Query decomposition into SQL + semantic layers |
| **NLP-based Job Market Analysis** | Skill extraction, sector classification |
| **LLM Skill Extraction** | Structured extraction from unstructured job descriptions |

---

## Repositories and team

This repository is Faiz Jabir's personal, professor-ready copy of the project.
The original shared team repository is maintained separately at
[AlbaraaAloush/ai-powered-job-market-intelligence](https://github.com/AlbaraaAloush/ai-powered-job-market-intelligence).

The team contributors are:

| Role | Contributor |
|---|---|
| RAG System, Pipeline, UI, Evaluation | Faiz Jabir |
| Data Collection & Preprocessing | Albaraa |
| Front-End |Yahya |
| Supervision | Dr. Hamdy |

**Institution:** Hamad Bin Khalifa University (HBKU) — QCRI Summer Internship 2026
