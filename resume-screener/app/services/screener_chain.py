import os
import json
from pathlib import Path
from dotenv import load_dotenv
import logfire
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()





PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text()


def build_screener_chain():

    system_prompt = load_prompt("system_prompt.txt")
    human_prompt = load_prompt("human_prompt.txt")

    llm = ChatGroq(
    model_name = os.getenv("MODEL_NAME"),
    groq_api_key = os.getenv("GROQ_API_KEY"),
    temperature = 0.1
    )


    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt)
    ])

    chain = prompt | llm | StrOutputParser()

    return chain


def screen_resume(resume_text: str, job_description: str) -> dict:

    chain = build_screener_chain()

    with logfire.span("llm.screen_resume", model=os.getenv("MODEL_NAME")):
        raw_output = chain.invoke({
            "resume_text": resume_text,
            "job_description": job_description
        })

    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"LLM returned invalid JSON: {raw_output}")

    return result
