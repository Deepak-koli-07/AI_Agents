# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Activate virtual environment (Windows)
source myvenv/Scripts/activate

# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `GROQ_API_KEY` — API key from Groq
- `MODEL_NAME` — Groq model to use (e.g. `llama-3.1-8b-instant`)

## Architecture

**FastAPI** app (`app/main.py`) exposes two endpoints:
- `GET /health` — health check
- `POST /screen` — accepts `ScreenRequest` (job description + resume text), returns `ScreenResponse` (match score 0–100, matched skills, skill gaps, summary)

**Data flow:**
1. Client POSTs job description + resume text to `/screen`
2. `main.py` validates input via Pydantic models (`app/models.py`)
3. Currently uses simple keyword-intersection matching (temporary); the intended path is through `screener_chain.py`
4. `screener_chain.py` builds a LangChain pipeline using Groq's LLM, loading prompts from `app/prompts/system_prompt.txt` and `app/prompts/human_prompt.txt`, and expects JSON-structured output

**PDF parsing** (`app/services/pdf_parser.py`) uses PyMuPDF (`fitz`) to extract and clean text — this is a utility, not yet wired into the API endpoint.

## Known Issues

- `app/services/screener_chain.py` uses `ChatPromptTemplate` without importing it — add `from langchain_core.prompts import ChatPromptTemplate`
- `app/prompts/system_prompt.txt` and `human_prompt.txt` are empty and need to be populated before the LLM chain works
- The `/screen` endpoint uses keyword matching instead of the LLM chain; `build_screener_chain()` needs to be integrated into `main.py`
