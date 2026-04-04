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

### system_prompt.txt — What the LLM is told to be

```
You are an expert technical recruiter and resume screener.
You will be given a resume and a job description.
Your job is to analyze how well the candidate matches the role.

You MUST respond with valid JSON only. No explanation, no markdown, no extra text.
Just raw JSON in exactly this format:

{
    "match_score": <integer between 0 and 100>,
    "matched_skills": [...],
    "gaps": [...],
    "summary": "<2-3 sentence summary>"
}
```

**Key decisions:**
- Role is set as *technical recruiter* — this biases the LLM toward understanding domain skills, not just word overlap.
- "MUST respond with valid JSON only" is explicit — reduces hallucinated prose before/after the JSON.
- `temperature=0.1` — low randomness for consistent, structured output.
- Curly braces in the JSON example are escaped as `{{` / `}}` — LangChain's `ChatPromptTemplate` uses `{variable}` syntax, so literal braces must be doubled to avoid being treated as template variables.

### human_prompt.txt — What the LLM receives per request

```
RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}

Analyze the match and respond with JSON only.
```

**Key decisions:**
- Resume comes first — the LLM reads it as context before evaluating against the JD.
- `{resume_text}` and `{job_description}` are LangChain template variables — filled at runtime by `chain.invoke(...)`.
- Ends with a re-instruction ("respond with JSON only") — reinforces the system prompt constraint.

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
