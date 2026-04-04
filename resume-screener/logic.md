# Resume Screener — Scoring Logic

## Core Principle: Always Use the LLM

Every screening request goes through the LLM — no keyword matching, no heuristics, no shortcuts.

**Why:**
- Keyword matching is naive. It would match "Python" in "I have no Python experience" and miss "built ML pipelines" when the JD asks for "machine learning".
- The LLM understands semantic meaning, synonyms, implied skills, and context. A recruiter doesn't just ctrl+F a resume — neither should the screener.
- `llama-3.1-8b-instant` has a **128K token context window**. A full resume + job description is ~1,500–2,500 tokens — less than 2% of the limit. There is no reason to chunk, summarize, or pre-filter.

---

## Full Scoring Flow

```
PDF bytes (from upload)
        │
        ▼
pdf_parser.py  — PyMuPDF extracts all page text, collapses whitespace
        │
        ▼
resume_text (clean string)
        │
        ▼
screener_chain.py — build_screener_chain()
        │
        ├── load system_prompt.txt   → LLM role + output format rules
        ├── load human_prompt.txt    → inject {resume_text} + {job_description}
        ├── ChatGroq(llama-3.1-8b-instant, temperature=0.1)
        └── StrOutputParser()
        │
        ▼
chain.invoke({"resume_text": ..., "job_description": ...})
        │
        ▼
raw string from LLM  (should be pure JSON)
        │
        ▼
json.loads(raw_output)
        │
        ▼
{
  "match_score": 0–100,
  "matched_skills": [...],
  "gaps": [...],
  "summary": "..."
}
        │
        ▼
ScreenResponse (Pydantic validates types + constraints)
        │
        ▼
JSON response to browser
```

---

## Prompt Design

### system_prompt.txt — Scoring rubric given to the LLM

The system prompt defines the LLM's role and a **structured 100-point rubric**:

| Dimension | Points | What it evaluates |
|---|---|---|
| Core Technical Skills | 40 | Required tools, languages, frameworks — exact + synonym matches |
| Experience & Seniority | 25 | Years of experience, seniority level, production vs side-project weight |
| Domain & Industry | 20 | Same or adjacent domain (e.g. fintech, MLOps, NLP) |
| Education & Certifications | 10 | Degree requirements, relevant certifications |
| Soft Skills | 5 | Communication, leadership, collaboration overlap |

**Score range definitions** are explicitly stated so the LLM anchors consistently:
- 90–100: near-perfect, strongly recommend
- 70–89: strong fit, worth interviewing
- 50–69: partial fit, notable gaps
- 30–49: weak fit, several required skills missing
- 0–29: poor fit, wrong domain or missing critical skills

**Synonym rules** prevent false negatives:
- "ML" = "machine learning" = "ML models"
- "GenAI" = "LLMs" = "large language models"
- "MLOps" = "ML engineering" = "model deployment"
- etc.

**Inference rules** from projects — e.g. if resume shows a RAG system → infer LangChain + vector DB experience even if not explicitly listed.

**Filler word exclusion** — words like "experience", "knowledge", "proficiency" are explicitly excluded from skill matching.

**Key technical decisions:**
- `temperature=0.1` — low randomness for consistent, structured output.
- Curly braces in the JSON example are escaped as `{{` / `}}` — LangChain's `ChatPromptTemplate` uses `{variable}` syntax, so literal braces must be doubled.

### human_prompt.txt — What the LLM receives per request

The human prompt puts the **JD first, resume second** — the LLM extracts requirements before reading the candidate's background. It then instructs the LLM to:

1. Extract required vs preferred skills from the JD
2. Score each rubric dimension
3. Sum into final match_score
4. List only confirmed matched skills (no guessing)
5. List only genuinely missing required skills as gaps
6. Write a 3–4 sentence summary with a hiring recommendation

`{resume_text}` and `{job_description}` are LangChain template variables filled at runtime by `chain.invoke(...)`.

---

## LangChain Chain

```python
chain = prompt | llm | StrOutputParser()
```

This is a simple three-step pipe:

| Step | Component | Purpose |
|---|---|---|
| 1 | `ChatPromptTemplate` | Merges system + human prompts with runtime variables |
| 2 | `ChatGroq` | Sends the formatted messages to Groq's API |
| 3 | `StrOutputParser` | Extracts the raw string content from the LLM response object |

After the chain runs, `json.loads()` converts the string to a Python dict. If the LLM returns malformed JSON, a `ValueError` is raised with the raw output included — making it easy to debug prompt failures.

---

## Why temperature=0.1

The output is structured JSON. Higher temperature = more creative = more likely to add prose, change field names, or wrap in markdown. At 0.1 the model is nearly deterministic for format while still reasoning about content.

---

## Observability

Every LLM call is wrapped in a Logfire span:

```python
with logfire.span("llm.screen_resume", model=os.getenv("MODEL_NAME")):
    raw_output = chain.invoke(...)
```

This records latency, model used, and any exceptions on the Logfire dashboard at:
`logfire-us.pydantic.dev/deepak-koli-07/resume-screener`

All requests are also logged locally via loguru to `logs/app.log` and visible at `GET /logs`.

---

## What the Score Means

| Range | Colour in UI | Interpretation |
|---|---|---|
| 70–100 | Green | Strong match — worth interviewing |
| 40–69 | Orange | Partial match — gaps exist but not disqualifying |
| 0–39 | Red | Weak match — significant skill gaps |

The score is determined entirely by the LLM based on the semantic content of both documents. There is no post-processing or re-weighting applied.
