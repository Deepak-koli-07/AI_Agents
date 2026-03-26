# Resume Screener — Architecture

---

## How a Request Flows

```
User (Swagger UI / API client)
        │
        │  POST /screen-pdf
        │  { job_description + PDF file }
        ▼
┌─────────────────────────────────────┐
│  FastAPI  (main.py)                 │
│  • HTTP middleware logs the request │
│  • /screen-pdf endpoint receives it │
└──────────────────┬──────────────────┘
                   │ PDF bytes
                   ▼
┌─────────────────────────────────────┐
│  pdf_parser.py                      │
│  • Opens PDF with PyMuPDF           │
│  • Extracts and cleans plain text   │
└──────────────────┬──────────────────┘
                   │ resume text
                   ▼
┌─────────────────────────────────────┐
│  screener_chain.py  (LangChain)     │
│                                     │
│  system_prompt.txt                  │
│  human_prompt.txt                   │
│         │                           │
│         ▼                           │
│  Groq LLM (llama-3.1-8b-instant)   │
│         │                           │
│         ▼                           │
│  Parse JSON output                  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  ScreenResponse  (models.py)        │
│  • match_score    (0–100)           │
│  • matched_skills (list)            │
│  • gaps           (list)            │
│  • summary        (string)          │
└──────────────────┬──────────────────┘
                   │
                   ▼
        User gets JSON response
```

---

## Observability

```
┌──────────────────────────────────────────────────────────────┐
│  Your App                                                    │
│                                                              │
│   FastAPI ──── loguru ──────────► logs/app.log              │
│      │                                    │                  │
│      │                                    ▼                  │
│      │                           /logs UI (localhost:8001)   │
│      │                                                       │
│      ├── instrument_fastapi ──► Logfire: request traces      │
│      │                                                       │
│      └── instrument_httpx ───► Logfire: Groq API HTTP calls  │
│                                                              │
│   LLM Chain ── logfire.span ──► Logfire: llm.screen_resume  │
│                                                              │
└──────────────────────────────────────────────────────────────┘

  Logfire Dashboard → logfire-us.pydantic.dev/deepak-koli-07/resume-screener
```

---

## File Structure

```
resume-screener/
├── app/
│   ├── main.py                 ← FastAPI app, endpoints, middleware
│   ├── models.py               ← Pydantic ScreenRequest / ScreenResponse
│   ├── logger.py               ← loguru setup, writes to logs/app.log
│   ├── log_viewer.py           ← /logs HTML UI served by FastAPI
│   ├── prompts/
│   │   ├── system_prompt.txt   ← LLM role + JSON output format
│   │   └── human_prompt.txt    ← JD + resume template variables
│   └── services/
│       ├── pdf_parser.py       ← PyMuPDF text extraction
│       └── screener_chain.py   ← LangChain pipeline + Groq LLM
├── logs/
│   └── app.log                 ← rotating log file (5 MB, 7 day retention)
├── ARCHITECTURE.md
├── CLAUDE.md
└── requirements.txt
```

---

## Input / Output

```
                    ┌─────────────────────┐
  job_description ──►                     ├──► match_score    (0–100)
                    │   Resume Screener   ├──► matched_skills (list)
  resume PDF     ──►                     ├──► gaps           (list)
                    └─────────────────────┘──► summary        (string)
```
