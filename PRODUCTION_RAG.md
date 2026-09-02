# Production RAG controls

The chat path now uses one evidence snapshot and one Langfuse root trace per request:

`request → injection guard → deterministic analytics or vector retrieval → sanitized context → generation → citation/number validation → response → feedback`

BM25, RRF, and cross-encoder reranking remain available for research runs via
`ENABLE_HYBRID_RETRIEVAL=true` and `ENABLE_RERANKER=true`. They are disabled by
default because the measured CPU cost added 10–13 seconds to each semantic
question on the target machine without benefiting deterministic analytics.

## Implemented controls

- `rag.request` is the Langfuse root. Child observations record decomposition, rewritten query, filters, SQL context, vector/BM25/RRF/reranker scores, exact sanitized context, generation, validation, abstention, approximate token counts, and version identifiers.
- Retrieved jobs use stable `JOB-<Qdrant UUID>` IDs; dataset and SQL evidence use `DATASET-1` and `SQL-1`. Unsupported citations or numbers cause abstention before the response reaches the browser.
- Retrieved text is untrusted. Instruction-like content is removed and flagged; direct prompt-injection requests are blocked and traced.
- Helpful/not-helpful feedback, reason, optional comment, and chat sessions are stored in managed PostgreSQL when `DATABASE_URL` is configured and sent to the corresponding Langfuse trace as a score. Anonymous usage events retain counts, language, response mode, latency, and success without IP addresses or raw question text. Local development falls back safely.
- `python RAG/build_index.py` validates input schemas and writes `RAG/reports/data_quality.json`. Incremental indexing removes Qdrant points absent from the canonical snapshot.
- `python RAG/build_runtime_data.py` converts Excel into a fingerprinted compact Parquet artifact. Normal restarts validate and load it instead of parsing workbooks.
- `RAG/evaluate_live_pipeline.py` runs 52 reviewed English/Arabic cases through the real `/api/chat` path, including latency, language, formatting, count consistency, evidence metadata, follow-ups, abstention, semantic RAG, and injection cases.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest RAG/tests -q --ignore=RAG/tests/test_live_api.py
Set-Location frontend; npm run build; Set-Location ..
.\.venv\Scripts\python.exe RAG/evaluate_live_pipeline.py --base-url http://localhost:8000
```

The live evaluation uses model API calls and writes `RAG/reports/live_evaluation.json`. Review failures rather than weakening its acceptance rules.

Langfuse handles LLM/RAG observability; Sentry handles application exceptions. Neither replaces Qdrant or the analytics database. Invite the supervisor as a project member instead of sharing a Gmail password, and rotate credentials exposed in screenshots or source control.
