---
title: File Converter API
emoji: 🔄
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: FastAPI backend for a local-first universal file converter
---

# Universal File Converter

> The block above is Hugging Face Spaces metadata. It is ignored by GitHub and
> by the local app.

A local-first file conversion web app. Next.js + TypeScript + Tailwind frontend,
FastAPI + Python backend. **No page limits, no watermarks, no account.**

Files are processed on your own machine and deleted automatically after a
configurable retention window.

---

## Why this exists

Hosted converters cap long files (a 100+ page PDF is exactly where most free
tiers start charging), add watermarks, or compress images. This runs entirely
locally, so the only limit is your disk and the `MAX_FILE_SIZE_MB` you set.

---

## Supported conversions

The backend is the **single source of truth**. `GET /api/formats` returns the
live matrix; the frontend never hard-codes it.

### Documents

| From | To |
| --- | --- |
| `PDF` | `DOCX` `TXT` `MD` `HTML` `CSV` `TSV` `XLSX` `JSON` `XML` `YAML` |
| `DOCX` | `PDF` `TXT` `MD` `HTML` `CSV` `JSON` `ODT`\* `RTF`\* `DOC`\* |
| `CSV` / `TSV` | `PDF` `XLSX` `JSON` `DOCX` `MD` `HTML` `TXT` `XML` `YAML` |
| `XLSX` | `PDF` `CSV` `TSV` `JSON` `DOCX` `HTML` `TXT` |
| `MD` | `PDF` `DOCX` `HTML` `TXT` `DOC`\* |
| `HTML` | `PDF` `DOCX` `TXT` `MD` |
| `TXT` | `PDF` `DOCX` `MD` `HTML` `DOC`\* |
| `JSON` | `CSV` `XLSX` `YAML` `MD` `HTML` `TXT` |
| `XML` | `HTML` `TXT` `CSV` `JSON` |
| `YAML` | `JSON` `CSV` `TXT` |

\* Requires LibreOffice. Without it these pairs are **hidden**, not faked.

### Images

Every raster format to every other: `JPG` `PNG` `WEBP` `GIF` `BMP` `TIFF` `ICO`
`AVIF`. Plus `SVG` → `PNG` / `JPG` / `WEBP` / `BMP` / `TIFF` / `PDF`.

`AVIF`/`HEIC` need `pillow-avif-plugin` (already in `requirements.txt`).

`SVG` raster output needs `svglib`, which is **not** installed by default: its
`pyppmd` dependency needs MSVC to build on Windows and has no wheel for
Python 3.13. Without it, `SVG` sources simply do not advertise raster targets
and the UI hides them. To enable on Python 3.12 or Linux:

```powershell
.\.venv\Scripts\python.exe -m pip install svglib
```

### Archives

`ZIP` ⇄ `TAR` ⇄ `TAR.GZ` ⇄ `BZIP2` ⇄ `XZ`, and `7Z` as a source.

`7Z` needs `py7zr`, which is in `requirements.txt` but depends on `pybcj`. If
`pybcj` cannot load, `7Z` sources are hidden and the other archive pairs keep
working. Bare `.gz`/`.bz2`/`.xz` (a single compressed file, not a tar) are
handled as single-member archives.

### Audio / Video

**Not implemented.** The converters were deliberately left out of this build.

### Conversions that are genuinely not supported

Rather than returning a broken file, these return
`unsupported_format`:

- `PNG` → `SVG` (that is vector tracing, not conversion)
- `SVG` → `ICO` (ICO needs a raster bitmap)
- Identical input/output formats
- `PDF` → `XLSX` for PDFs that contain no ruled table (extraction returns text,
  not a spreadsheet)

---

## Requirements

| | |
| --- | --- |
| **Python** | 3.11+ (tested on 3.13) |
| **Node** | 20+ (tested on 24) |
| **LibreOffice** | *Optional.* Needed for `DOC`/`ODT`/`RTF`/`XLS` |

No database, no message queue. Everything runs locally. A `Dockerfile` is
included for deployment (see [Deployment](#deployment)) but is not needed
locally.

---

## Setup

### 1. Backend

```powershell
cd file-converter\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start it:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

> **Windows note:** if the Next.js build runs out of memory, set
> `$env:NODE_OPTIONS="--max-old-space-size=6144"` before `npm run build`.

### 2. Frontend

```powershell
cd file-converter\frontend
npm install
npm run dev
```

Open http://localhost:3000

If the backend is not on port 8000, set it in `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Optional: LibreOffice

Only needed for `DOC`, `ODT`, `RTF` and `XLS`.

- **Windows** — install from libreoffice.org, then either add its `program`
  folder to `PATH` or set `LIBREOFFICE_PATH` in `backend/.env`:
  ```
  LIBREOFFICE_PATH=C:\Program Files\LibreOffice\program\soffice.exe
  ```
- **macOS** — `brew install --cask libreoffice`
- **Linux** — `sudo apt install libreoffice`

Check whether it was picked up:

```powershell
Invoke-RestMethod http://localhost:8000/api/health |
  Select-Object -ExpandProperty dependencies
```

---

## Configuration

Copy `backend/.env.example` to `backend/.env`. Every value is read at startup.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAX_FILE_SIZE_MB` | `500` | Per-file upload cap |
| `FILE_RETENTION_MINUTES` | `30` | When temp files are deleted |
| `CLEANUP_INTERVAL_SECONDS` | `300` | How often the sweeper runs |
| `UPLOAD_DIR` / `OUTPUT_DIR` | `./temp/...` | Storage (relative to `backend/`) |
| `MAX_CONCURRENT_JOBS` | `4` | Parallel conversions |
| `CONVERSION_TIMEOUT_SECONDS` | `900` | Per-conversion timeout |
| `LIBREOFFICE_PATH` | `soffice` | Path to the binary |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowlist |

---

## API

All responses share one envelope:

```json
{ "success": true, "data": {}, "error": null, "code": null }
```

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness + dependency report |
| `GET` | `/api/formats` | Supported formats and conversion matrix |
| `POST` | `/api/upload` | Upload a file (`multipart/form-data`, field `file`) |
| `GET` | `/api/files/{id}` | Upload details |
| `DELETE` | `/api/files/{id}` | Delete an upload now |
| `POST` | `/api/convert` | Queue a job → `202` |
| `GET` | `/api/conversions/{id}` | Job status (poll this) |
| `GET` | `/api/download/{id}` | Download the result |
| `DELETE` | `/api/conversions/{id}` | Delete the result now |

### Walkthrough

```bash
# 1. upload
curl -F "file=@report.pdf" http://localhost:8000/api/upload
# -> { "data": { "id": "abc...", "extension": "pdf",
#               "available_formats": ["docx","csv","txt", ...] } }

# 2. convert
curl -X POST http://localhost:8000/api/convert \
     -H "Content-Type: application/json" \
     -d '{"file_id":"abc...","target_format":"csv"}'
# -> 202 { "data": { "id": "job...", "status": "queued" } }

# 3. poll
curl http://localhost:8000/api/conversions/job...
# -> { "data": { "status": "processing", "progress": 45, "stage": "Encoding" } }
# -> { "data": { "status": "completed", "output_name": "report.csv" } }

# 4. download
curl -OJ http://localhost:8000/api/download/job...
```

### Job model

```json
{
  "id": "…", "status": "queued|processing|completed|failed",
  "progress": 0, "stage": "Encoding",
  "source_name": "report.pdf", "target_extension": "csv",
  "output_name": "report.csv", "output_size_bytes": 20481,
  "error": null,
  "created_at": "2026-01-01T00:00:00+00:00",
  "updated_at": "2026-01-01T00:00:02+00:00"
}
```

### Error codes

| Code | HTTP | Message shown |
| --- | --- | --- |
| `unsupported_format` | 400 | Sorry, this file format is not supported. |
| `validation_error` | 422 | The request was not valid. |
| `file_not_found` | 404 | The requested file could not be found. |
| `file_too_large` | 413 | Your file exceeds the maximum allowed size. |
| `conversion_failed` | 422 | We couldn't convert this file. Please try again. |
| `dependency_missing` | 503 | A required tool is unavailable on this server. |
| `server_error` | 500 | Something went wrong. Please try again later. |

Python stack traces are never returned. Details go to the backend log only.

---

## Architecture

```
file-converter/
├── backend/
│   ├── app/
│   │   ├── main.py              app factory, CORS, lifespan
│   │   ├── config.py            env-driven Settings
│   │   ├── api/
│   │   │   ├── dependencies.py  DI + error envelope
│   │   │   └── routes/          health.py, files.py, conversions.py
│   │   ├── converters/          the plugin system
│   │   │   ├── base.py          BaseConverter + ConverterRegistry
│   │   │   ├── formats.py       format metadata, aliases, blocklist
│   │   │   ├── image_converter.py
│   │   │   ├── document_converter.py
│   │   │   ├── document_model.py     shared IR
│   │   │   ├── document_readers.py   format -> IR
│   │   │   ├── document_writers.py   IR -> format
│   │   │   └── archive_converter.py
│   │   ├── services/            store, file, conversion, cleanup
│   │   ├── models/schemas.py    Pydantic schemas
│   │   └── utils/               security, executor, errors, logging
│   ├── tests/
│   ├── temp/{uploads,outputs}   randomised names, auto-cleaned
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                 layout, page, globals.css
│   │   ├── components/          reusable components
│   │   ├── hooks/useConverter.ts the state machine
│   │   ├── lib/api.ts           the only place fetch is called
│   │   ├── lib/format.ts        byte/label helpers
│   │   └── types/               TypeScript types
│   ├── next.config.ts
│   ├── vercel.json              Vercel build config
│   └── .env.example
├── Dockerfile                   Hugging Face Spaces image
├── .dockerignore
├── .gitignore
└── README.md
```

### How document conversion works

Naive converters hard-code every pair (N×M code paths). Instead:

```
file -> Reader -> DocumentModel -> Writer -> file
```

A `DocumentModel` is a list of typed blocks (heading, paragraph, list, code,
table). Each supported *input* format has a reader; each supported *output*
format has a writer. Adding `ODT` output means writing one function, not
fifty-six pairs.

The same model powers the cross-format shortcuts — `PDF → CSV` refines the
model toward its tabular form first, so ruled tables survive the round trip.

### Adding a converter

```python
# backend/app/converters/my_converter.py
from app.converters.base import BaseConverter, ConversionContext
from app.models.schemas import Category

class MyConverter(BaseConverter):
    name = "my-format"
    category = Category.DOCUMENT
    source_formats = frozenset({"foo"})
    target_formats = frozenset({"pdf", "txt"})

    def convert(self, input_path, output_path, context=None):
        ctx = self._context(context)
        ctx.update(50, "Converting")
        output_path.write_bytes(input_path.read_bytes())
        ctx.update(100, "Complete")
        return output_path
```

Register it in `backend/app/converters/__init__.py`:

```python
instance.register(MyConverter())
```

`GET /api/formats` picks it up automatically and the UI renders the new
options. No route, service or frontend change required.

---

## Security

Uploads are untrusted input. What this app does:

- **Extension allowlist** driven by the converter registry, plus a hard
  blocklist for executables (`.exe`, `.bat`, `.ps1`, `.sh`, `.jar`, …).
- **MIME cross-check** — a declared type that contradicts the extension is
  rejected. Browsers send loose MIME types, so generic types are allowed
  through and only genuine mismatches fail.
- **Randomised storage names** (`<token>.<ext>`). The user's filename is
  sanitised for *display only* and never touches a filesystem path.
- **Size cap enforced while streaming** in 1 MB chunks, so a huge upload is
  cut off without ever loading into memory.
- **Path traversal protection** — every resolved path is verified to sit
  inside its base directory; archives are checked member-by-member for `..`,
  absolute paths and Windows drive letters.
- **Zip-bomb guards** — member count and total expanded size are capped at
  50,000 files / 2 GB.
- **No execution of uploads.** External tools run via `subprocess` with an
  argument list and `shell=False`; user filenames are never interpolated into
  a command line.
- **Automatic cleanup** after `FILE_RETENTION_MINUTES`, plus eager deletion
  via `DELETE /api/files/{id}`.
- **No secrets in the repo.** All configuration is environment-driven.
- Logs record ids, extensions and byte counts — never file contents.

---

## Performance notes

- Uploads stream to disk; conversion output is written to disk. Large files
  are not held in memory.
- `PDF` extraction is **page by page** (pdfplumber), which is what makes
  100+ page files workable.
- Long documents are paginated by reportlab, not laid out by hand.
- `MAX_CONCURRENT_JOBS` bounds parallel work so a burst cannot exhaust CPU.
- Frontend polls every 700 ms only while a job is running, and stops on
  unmount, so a finished page leaves no timers behind.
- Windows builds may need `$env:NODE_OPTIONS="--max-old-space-size=6144"`.

---

## Tests

```powershell
cd file-converter\backend
.\.venv\Scripts\python.exe -m pytest -v
```

Covers upload validation, size limits, MIME mismatch, path traversal,
format detection, converter selection, the plugin registry, real image and
document conversions, `PDF → CSV` table extraction, archive repacking,
archive traversal rejection, job status, download headers and cleanup.

There is also a smoke suite that runs against a **live** server and exercises
15 real conversions end to end:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   # terminal 1
.\.venv\Scripts\python.exe tests\smoke_e2e.py                      # terminal 2
```

Frontend checks:

```powershell
cd file-converter\frontend
npm run lint
npx tsc --noEmit
npm run build
```

---

## Deployment

Two deployables in one repo: the FastAPI backend goes to **Hugging Face
Spaces** (Docker SDK), the Next.js frontend goes to **Vercel**.

```
GitHub ──► file-converter (source of truth)
             ├── backend/  ──► HF Space   (Dockerfile at repo root, port 7860)
             └── frontend/ ──► Vercel    (root dir = frontend, output .next)
```

### 1. Backend → Hugging Face Spaces

Create a **Docker** space at <https://huggingface.co/new-space>, then push:

```powershell
cd file-converter
git remote add hf https://huggingface.co/spaces/<user>/<space>
git push hf main
```

Or let the Space clone the GitHub repo directly and rebuild on every push.

Set these as **Variables and secrets** in the Space settings:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `CORS_ORIGINS` | your Vercel URL, e.g. `https://file-converter.vercel.app` |
| `MAX_FILE_SIZE_MB` | `500` |
| `FILE_RETENTION_MINUTES` | `30` |
| `LIBREOFFICE_PATH` | `soffice` |

The space URL is `https://<user>-<space>.hf.space`; API lives under `/api`.

`INSTALL_LIBREOFFICE=true` is the default build arg, so the legacy
`DOC`/`ODT`/`RTF`/`XLS` pairs are available in the cloud build. Set it to
`false` for a much smaller, faster image that drops those pairs.

> HF Spaces free tier has ephemeral disk. Temp files live on the container
> filesystem, which is what you want for a retention-based delete anyway.

### 2. Frontend → Vercel

```powershell
cd file-converter\frontend
npx vercel --prod
```

On first run Vercel will ask for the project settings. Use:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Build Command | `npm run build` |
| Output Directory | `.next` |
| Install Command | `npm ci` |

Then add the environment variable for all environments:

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://<user>-<space>.hf.space` |

Redeploy after setting it, since `NEXT_PUBLIC_*` values are inlined at build
time.

### 3. CORS

Both sides must agree. The Vercel origin goes in the Space's `CORS_ORIGINS`,
and the Space URL goes in Vercel's `NEXT_PUBLIC_API_URL`. Restart the Space
after changing a variable.

### 4. Verify

```powershell
# backend
curl https://<user>-<space>.hf.space/api/health
# -> {"success":true,"data":{"status":"ok",...}}

# frontend
curl -I https://<your-app>.vercel.app
```

Load the Vercel URL, upload a CSV, and confirm the target list is populated —
that proves CORS and the formats endpoint in one step.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Can't reach the conversion server" | Backend is not on :8000, or CORS blocked it. Check `/api/health`. |
| Format list won't load | Same as above. The banner on the page shows the exact command to run. |
| `DOC`/`ODT`/`RTF`/`XLS` missing | LibreOffice not installed — set `LIBREOFFICE_PATH`, restart. |
| `PDF → CSV` returns one column | The PDF has no ruling lines, so no table was detectable. Text is still extracted. |
| `PDF` conversion says "needs OCR" | The PDF is a scan. Install Tesseract and wire it in as a reader. |
| Next.js build runs out of memory | `$env:NODE_OPTIONS="--max-old-space-size=6144"` |
| `AVIF` fails | Reinstall so `pillow-avif-plugin` is present. |

---

## Not in this build

Deliberately excluded to keep the MVP focused: audio/video, accounts, payments,
databases, batch conversion, WebSockets (polling is used instead), rate
limiting, cloud storage and history.

The store is an interface (`app/services/store.py`), so a database or Redis
backend can replace the in-memory implementation without touching routes.
