# Mihna frontend

The Next.js dashboard reads a versioned static snapshot from
`public/data/dashboard`. It does not call FastAPI, parse Excel, or wait for the
optional RAG service.

## Local dashboard

From the repository root:

```powershell
.\scripts\start-local.ps1
```

Open <http://localhost:3000/app>.

## Refresh the data

Only when the source files in `RAG/data` change:

```powershell
.\scripts\build-dashboard-data.ps1
```

Commit the generated manifest, analytics snapshot, and posting shards under
`public/data/dashboard` so Vercel can serve them directly from its CDN.

## Optional local chat

```powershell
.\scripts\start-local.ps1 -WithRag
```

The chat still uses the Python RAG backend for now. Dashboard availability does
not depend on its startup or health.

Copy `.env.example` to `.env.local` for local work. On Vercel, set
`NEXT_PUBLIC_API_URL` to the public HTTPS URL of the deployed Python API; a
localhost value cannot work for visitors.

## Verification

```powershell
.\scripts\test-local.ps1
```
