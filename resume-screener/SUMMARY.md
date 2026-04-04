# Resume Screener — Project Summary

## What We Built

An AI-powered resume screening web app that takes a PDF resume and a job description, and returns a match score, matched skills, skill gaps, and a human-readable summary — all powered by an LLM.

---

## Step-by-Step Journey

### 1. Project Already Had a Skeleton
The project started with a basic FastAPI structure already in place:
- `app/main.py` — had a `/health` and `/screen` endpoint but using **simple keyword matching** (matching stopwords like "and", "the", "of" as skills — completely wrong)
- `app/models.py` — Pydantic models for request/response
- `app/services/screener_chain.py` — LangChain chain was written but had a **missing import bug** (`ChatPromptTemplate` not imported)
- `app/prompts/system_prompt.txt` and `human_prompt.txt` — **both empty**
- No PDF upload support

---

### 2. Fixed PDF Upload (Swagger UI)
**Problem:** The `/screen` endpoint only accepted JSON. There was no way to upload a PDF file in Swagger UI.

**Fix:** Added a new `/screen-pdf` endpoint using `UploadFile` + `Form` (multipart) so Swagger UI shows a file picker. Wired in the existing `pdf_parser.py` which uses **PyMuPDF** to extract text from PDF bytes.

---

### 3. Fixed the LLM Chain
**Problems found:**
- `screener_chain.py` was missing `from langchain_core.prompts import ChatPromptTemplate`
- Both prompt files were empty
- The `/screen-pdf` endpoint was still using keyword matching, not the LLM

**Fixes:**
- Added the missing import
- Wrote `system_prompt.txt` — tells the LLM to act as a recruiter, extract only meaningful skills, and return strict JSON
- Wrote `human_prompt.txt` — template with `{job_description}` and `{resume_text}` variables
- Hit another bug: curly braces `{}` in the system prompt were treated as LangChain template variables — fixed by escaping them as `{{}}`
- Replaced keyword matching in both endpoints with `screen_resume()` from `screener_chain.py`

---

### 4. Added Logging with Loguru
Added a proper logging system so errors and events are visible:
- `app/logger.py` — loguru setup, logs to console and `logs/app.log` (rotates at 5MB, keeps 7 days)
- HTTP middleware in `main.py` logs every request and response
- Every endpoint logs key events: file name, chars extracted, score, errors with full tracebacks

---

### 5. Built a Log Viewer UI
Since the user wanted a UI to monitor what's happening:
- `app/log_viewer.py` — serves a dark-themed HTML page at `/logs`
- Auto-refreshes every 3 seconds
- Filter by log level (INFO / WARNING / ERROR) and keyword search
- Color-coded lines: red for errors, yellow for warnings, green for success

---

### 6. Added Logfire for Observability
For production-grade tracing of both the app and LLM calls:
- Installed `logfire[fastapi]` and `logfire[httpx]`
- `logfire.instrument_fastapi(app)` — traces every HTTP request with latency and status
- `logfire.instrument_httpx()` — traces the actual HTTP calls to Groq's API
- `logfire.span("llm.screen_resume")` — wraps the LangChain chain call so it appears as a named span in the dashboard
- Dashboard: **logfire-us.pydantic.dev/deepak-koli-07/resume-screener**

---

### 7. Tested with a Real Resume
Tested with Deepak's resume against an AI Engineer job description:

```
Match Score : 85 / 100
Matched     : Python, ML, LangChain, RAG, NLP, TensorFlow, BigQuery, SQL, Pandas, Groq, Prompt Engineering, and 29 more
Gaps        : Cloud AI services, GenAI models, Deep learning, Neural networks, Chatbots, Image processing
Summary     : Strong data analytics and AI background. Lacks cloud AI and deep learning experience.
```

---

### 8. Built an HTML Frontend
Replaced Swagger UI with a proper web interface:
- `app/static/index.html` — fully self-contained, no external dependencies
- Drag & drop PDF upload
- Job description textarea
- Animated score bar (green ≥70, orange ≥40, red <40)
- Matched skills as green tags, gaps as red tags
- Summary with styled left border
- Loading state with spinner while LLM is processing
- Served by FastAPI at `GET /`

---

### 9. Set Up Deployment

**Files added:**
- `Dockerfile` — builds the app image, exposes port 7860 for HF Spaces
- `railway.toml` — Railway deployment config
- `.dockerignore` — excludes `myvenv/`, `.env`, PDFs, logs from the image
- `README.md` — HF Spaces metadata (title, emoji, sdk: docker)

**Updated `.gitignore`** at the root `C:\AI_Agents` level to exclude `myvenv/`, `logs/`, and `*.pdf` before committing.

---

### 10. Pushed to GitHub and Hugging Face Spaces

- Committed and pushed all 16 files to **github.com/Deepak-koli-07/AI_Agents** under `resume-screener/`
- Created a Docker Space on Hugging Face as **BlueNeuron/resume-screener**
- Uploaded all source files to the Space
- Set `MODEL_NAME` as a Space secret
- Remaining secrets to add manually in HF Space settings: `GROQ_API_KEY`, `LOGFIRE_TOKEN`

**Live URL (after secrets are set):** https://huggingface.co/spaces/BlueNeuron/resume-screener

---

## Final Architecture

```
Browser (HTML Frontend)
        │
        │  POST /screen-pdf  (PDF + job description)
        ▼
┌──────────────────────────────────────┐
│  FastAPI  (main.py)                  │
│  • HTTP middleware  →  loguru logs   │
│  • /screen-pdf endpoint              │
│  • GET /  → serves index.html        │
│  • GET /logs  → log viewer UI        │
└────────────────┬─────────────────────┘
                 │
         ┌───────┴────────┐
         ▼                ▼
  pdf_parser.py     (if JSON: resume_text direct)
  PyMuPDF extract
         │
         ▼
┌──────────────────────────────────────┐
│  screener_chain.py  (LangChain)      │
│  prompts → Groq LLM → parse JSON    │
└────────────────┬─────────────────────┘
                 │
                 ▼
        ScreenResponse
        match_score / matched_skills / gaps / summary
                 │
                 ▼
            Browser


OBSERVABILITY
  loguru  →  logs/app.log  →  /logs UI
  Logfire →  request traces + LLM spans  →  logfire dashboard
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Web framework | FastAPI |
| LLM provider | Groq (llama-3.1-8b-instant) |
| LLM orchestration | LangChain |
| PDF parsing | PyMuPDF (fitz) |
| Data validation | Pydantic |
| Local logging | loguru |
| Observability | Logfire |
| Frontend | HTML / CSS / JS (served by FastAPI) |
| Hosting | Hugging Face Spaces (Docker) |
| Source control | GitHub |
