import os
import json
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

import gradio as gr

# LangChain / LLM
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# RAG components
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma


# ======================================================
# 0. ENV & BASIC SETUP
# ======================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.1-70b-versatile")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in the environment.")


# ======================================================
# 1. SCHEMA: SINGLE SOURCE OF TRUTH
# ======================================================

EVENT_TABLE_COLUMNS = [
    "event_date",
    "event_timestamp",
    "user_id",
    "session_id",
    "event_name",
    "page_url",
    "page_path",
    "content_category",
    "content_id",
    "traffic_source",
    "traffic_medium",
    "traffic_campaign",
    "device_category",
    "os",
    "country",
    "city",
    "is_logged_in",
    "user_type",
    "event_value",
    "engagement_time_ms",
    "scroll_depth_percent",
]


def is_schema_question(q: str) -> bool:
    q = q.lower()
    return any(
        word in q
        for word in [
            "column",
            "columns",
            "schema",
            "fields",
            "structure of event_table",
            "what columns do we have",
            "list all columns",
            "list all fields",
        ]
    )


def build_schema_response():
    cols_list = "\n".join(f"- {c}" for c in EVENT_TABLE_COLUMNS)
    mentor_text = (
        "The `event_table` has the following columns:\n\n" + cols_list
    )
    insight_text = (
        "These are all the columns available in `event_table`:\n\n" + cols_list
    )
    return mentor_text, insight_text


def is_concept_question(q: str) -> bool:
    """
    Detect questions that are about concepts / methods,
    not about pulling actual numbers from the dataset.
    """
    q_low = q.lower().strip()

    # Very generic / meta / capability questions
    meta_phrases = [
        "what can you do",
        "what can you help with",
        "how can you help",
        "what are you",
        "who are you",
    ]
    if any(p in q_low for p in meta_phrases):
        return True

    # Conceptual phrases
    concept_keywords = [
        "what is a funnel",
        "what is funnel analysis",
        "explain funnel",
        "how to do funnel",
        "what is retention",
        "what is cohort",
        "explain cohort",
        "what is dau",
        "what is wau",
        "what is mau",
        "difference between dau and mau",
        "how would you measure",
        "how to measure",
        "how to analyse",
        "how to analyze",
        "explain in simple terms",
        "what is time-series",
        "what is time series",
        "what is conversion rate",
        "what is bounce rate",
        "what is attribution",
        "what is segmentation",
        "concept",
        "theory",
    ]
    if any(k in q_low for k in concept_keywords):
        return True

    # Heuristic: questions starting with "what is", "how does" are often conceptual
    starters = ["what is ", "how does ", "how do i "]
    if any(q_low.startswith(s) for s in starters):
        # But if they clearly ask for counts / top / last N days, it's data
        data_words = ["count", "top", "last", "per day", "per week", "per month"]
        if not any(dw in q_low for dw in data_words):
            return True

    return False


# ======================================================
# 2. LLM CLIENT
# ======================================================

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name=MODEL_NAME,
    temperature=0.1,
)


# ======================================================
# 3. LOAD PROMPTS (SQL + INSIGHT)
# ======================================================

with open("prompts/sql_system_prompt.txt", "r", encoding="utf-8") as f:
    sql_system_prompt = f.read()

with open("prompts/insight_system_prompt.txt", "r", encoding="utf-8") as f:
    insight_system_prompt = f.read()


# ======================================================
# 4. RAG: LOAD ANALYTICS PLAYBOOK INTO CHROMA
# ======================================================

playbook_path = "analytics_playbook.md"
if not Path(playbook_path).exists():
    raise FileNotFoundError(f"{playbook_path} not found. Make sure it exists.")

loader = TextLoader(playbook_path, encoding="utf-8")
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
)
chunks = text_splitter.split_documents(docs)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma.from_documents(
    chunks,
    embedding=embeddings,
    persist_directory="chroma_analytics_playbook",
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 4})


# ======================================================
# 5. ANALYTICS MENTOR AGENT (CONCEPT EXPLAINER)
# ======================================================

analytics_system_prompt = """
You are an Analytics Mentor for product & event data.

You answer questions using ONLY the provided context, which comes from
analytics_playbook.md (event analytics playbook for event_table).

Your job:
- explain concepts (funnels, retention, cohorts, DAU/WAU/MAU, etc.)
- clarify which metrics/denominators to use
- describe how analyses are usually done
- connect ideas to the event_table schema when helpful

Rules:
- Do NOT invent new metrics that contradict the context.
- If something is not in the context, say you are not sure instead of guessing.
- You do NOT generate SQL here. You only explain concepts.
- Use simple, clear language that non-technical users can understand.
"""

analytics_prompt = ChatPromptTemplate.from_messages([
    ("system", analytics_system_prompt),
    ("human",
     "User question:\n{question}\n\n"
     "Relevant context from analytics_playbook.md:\n\n{context}\n\n"
     "Now answer the user's question using this context in simple terms.")
])

analytics_chain = analytics_prompt | llm | StrOutputParser()


def ask_analytics_mentor(question: str) -> str:
    docs = retriever.invoke(question)
    context = "\n\n".join(d.page_content for d in docs)
    answer = analytics_chain.invoke({
        "question": question,
        "context": context
    })
    return answer


# ======================================================
# 6. SQL GENERATION AGENT
# ======================================================

sql_prompt = ChatPromptTemplate.from_messages([
    ("system", sql_system_prompt),
    ("human",
     "Analytics guidance (may help you understand the intent):\n{analytics_context}\n\n"
     "User question:\n{user_input}\n\n"
     "Now return ONLY a single SQL SELECT query on event_table that answers the user question.")
])

sql_chain = sql_prompt | llm


# ======================================================
# 7. INSIGHT AGENT
# ======================================================

insight_prompt = ChatPromptTemplate.from_messages([
    ("system", insight_system_prompt),
    ("human",
     "User question:\n{user_question}\n\n"
     "SQL executed:\n```sql\n{sql_query}\n```\n\n"
     "Result preview:\n{data_preview}\n\n"
     "Relevant context from analytics_playbook.md:\n\n{playbook_context}\n\n"
     "Explain what this result means in simple language. "
     "Highlight key insights and, if possible, suggest 1–2 practical actions.")
])

insight_chain = insight_prompt | llm | StrOutputParser()


# ======================================================
# 8. DUCKDB: LOAD CSV INTO event_table
# ======================================================

# Adjust path if your CSV is elsewhere
csv_path = "events/events_part_1.csv"
if not Path(csv_path).exists():
    raise FileNotFoundError(f"{csv_path} not found. Make sure your CSV is in events/.")

duckdb.sql(f"""
    CREATE OR REPLACE TABLE event_table AS 
    SELECT * 
    FROM read_csv_auto('{csv_path}')
""")


def run_sql_to_df(sql: str) -> pd.DataFrame:
    """
    Execute SQL safely against DuckDB.
    Enforces:
    - only SELECT
    - only event_table (no information_schema, no other tables)
    """
    sql_clean = sql.strip()
    sql_lower = sql_clean.lower()

    if sql_lower.startswith("--"):
        raise ValueError(f"SQL agent refused: {sql_clean}")

    if not sql_lower.startswith("select"):
        raise ValueError("❌ Only SELECT statements are allowed.")

    forbidden = [
        "insert", "update", "delete", "drop", "alter",
        "truncate", "merge", "create", "replace"
    ]
    if any(word in sql_lower for word in forbidden):
        raise ValueError("❌ Unsafe SQL detected. Only SELECT on event_table is allowed.")

    # must query event_table; no information_schema or other tables
    if "event_table" not in sql_lower:
        raise ValueError("❌ SQL must query only from event_table.")

    if "information_schema" in sql_lower:
        raise ValueError("❌ Metadata / information_schema queries are not allowed.")

    return duckdb.sql(sql_clean).df()


# Quick sanity check (can comment out later)
_ = run_sql_to_df("SELECT * FROM event_table LIMIT 5")


# ======================================================
# 9. ORCHESTRATOR: FULL ANALYSIS PIPELINE
# ======================================================

def full_analysis(question: str):
    """
    Main pipeline:

    0) If question is about schema/columns → answer directly (no SQL)
    0.5) If question is conceptual → mentor only (no SQL)
    1) Mentor: conceptual explanation (RAG)
    2) SQL Agent: generate SELECT on event_table using mentor guidance
    3) DuckDB: run query
    4) Insight Agent: explain result
    """

    # 0) Schema / column questions
    if is_schema_question(question):
        mentor_answer, insight_answer = build_schema_response()
        return {
            "mentor": mentor_answer,
            "sql": "-- Not applicable (schema question answered directly).",
            "df": None,
            "insight": insight_answer,
        }

    # 0.5) Concept-only questions (no SQL needed)
    if is_concept_question(question):
        mentor_answer = ask_analytics_mentor(question)
        return {
            "mentor": mentor_answer,
            "sql": "-- Not applicable (conceptual analytics question, no SQL needed).",
            "df": None,
            "insight": mentor_answer,
        }

    # 1) Mentor / concept explanation (for context to SQL agent)
    mentor_answer = ask_analytics_mentor(question)

    # 2) SQL generation
    sql_query = sql_chain.invoke({
        "user_input": question,
        "analytics_context": mentor_answer,
    }).content.strip()

    # If SQL agent refused
    if sql_query.startswith("--"):
        return {
            "mentor": mentor_answer,
            "sql": sql_query,
            "df": None,
            "insight": "The SQL agent could not answer this question for event_table."
        }

    # 3) Execute SQL with guardrails
    try:
        df = run_sql_to_df(sql_query)
    except Exception as e:
        return {
            "mentor": mentor_answer,
            "sql": sql_query,
            "df": None,
            "insight": f"⚠️ SQL execution failed or was blocked:\n{e}"
        }

    # 4) Prepare preview & call insight agent
    if df is None or df.empty:
        data_preview = "No rows returned."
    else:
        data_preview = df.head(20).to_markdown(index=False)

    docs_for_insight = retriever.invoke(question)
    playbook_context = "\n\n".join(d.page_content for d in docs_for_insight)

    insight = insight_chain.invoke({
        "user_question": question,
        "sql_query": sql_query,
        "data_preview": data_preview,
        "playbook_context": playbook_context,
    })

    return {
        "mentor": mentor_answer,
        "sql": sql_query,
        "df": df,
        "insight": insight,
    }


# ======================================================
# 10. GRADIO APP
# ======================================================

def gradio_chat(message, history):
    res = full_analysis(message)

    reply_parts = []

    # Conceptual explanation
    reply_parts.append("🧠 **Conceptual explanation (from analytics playbook / mentor)**\n")
    reply_parts.append(res["mentor"])

    # SQL
    reply_parts.append("\n\n🧾 **Generated SQL (event_table only)**\n")
    reply_parts.append(f"```sql\n{res['sql']}\n```")

    # Insight
    reply_parts.append("\n\n📊 **Data insight (from query result)**\n")
    reply_parts.append(res["insight"])

    return "\n".join(reply_parts)


demo = gr.ChatInterface(
    fn=gradio_chat,
    title="🧠 AI Event Data Analyst",
    description=(
        "1) Understands your question using an analytics playbook (RAG)\n"
        "2) Generates SQL on `event_table` when needed\n"
        "3) Runs it in DuckDB and explains the result in simple language.\n\n"
        "Ask things like:\n"
        "- where are most users coming from?\n"
        "- are mobile users more than desktop?\n"
        "- explain funnel from page_view to subscription_start\n"
        "- what is retention analysis?\n"
    )
)


if __name__ == "__main__":
    # On Hugging Face Spaces, do NOT force port; just `demo.launch()`
    # For local dev, you can specify host/port if you want.
    demo.launch()
