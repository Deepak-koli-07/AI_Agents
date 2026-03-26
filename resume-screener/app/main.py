import traceback
from pathlib import Path
import logfire
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.models import ScreenRequest, ScreenResponse
from app.services.pdf_parser import extract_text_from_pdf
from app.services.screener_chain import screen_resume
from app.logger import logger
from app.log_viewer import LOG_UI_HTML, get_log_content

logfire.configure()
logfire.instrument_httpx()

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Resume Scanner")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
logfire.instrument_fastapi(app)


@app.get("/", response_class=FileResponse, include_in_schema=False)
def frontend():
    return FileResponse(STATIC_DIR / "index.html")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"REQUEST  {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"RESPONSE {request.method} {request.url.path} → {response.status_code}")
        return response
    except Exception as exc:
        logger.critical(f"UNHANDLED EXCEPTION on {request.method} {request.url.path}\n{traceback.format_exc()}")
        raise


@app.get("/health")
def health_check():
    logger.success("Health check OK")
    return {"status": "ok"}


@app.post("/screen", response_model=ScreenResponse)
def screen_resume_json(request: ScreenRequest):
    if not request.resume_text:
        logger.warning("POST /screen — resume_text was empty")
        raise HTTPException(status_code=400, detail="Resume text cannot be empty")

    logger.info("POST /screen — running LLM screener (JSON mode)")
    try:
        result = screen_resume(
            resume_text=request.resume_text,
            job_description=request.job_description
        )
        logger.success(f"POST /screen — score={result.get('match_score')}")
        return ScreenResponse(**result)
    except Exception as e:
        logger.error(f"POST /screen — screener failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/screen-pdf", response_model=ScreenResponse)
async def screen_resume_pdf(
    job_description: str = Form(...),
    resume_file: UploadFile = File(...)
):
    if not job_description.strip():
        logger.warning("POST /screen-pdf — job_description was empty")
        raise HTTPException(status_code=400, detail="Job description cannot be empty")

    logger.info(f"POST /screen-pdf — file='{resume_file.filename}'")
    try:
        file_bytes = await resume_file.read()
        resume_text = extract_text_from_pdf(file_bytes)
        logger.debug(f"PDF parsed — {len(resume_text)} chars extracted")

        result = screen_resume(
            resume_text=resume_text,
            job_description=job_description
        )
        logger.success(f"POST /screen-pdf — score={result.get('match_score')} file='{resume_file.filename}'")
        return ScreenResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"POST /screen-pdf — failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Log viewer UI ──────────────────────────────────────────────
@app.get("/logs", response_class=HTMLResponse, include_in_schema=False)
def logs_ui():
    return HTMLResponse(content=LOG_UI_HTML)


@app.get("/logs/raw", response_class=PlainTextResponse, include_in_schema=False)
def logs_raw():
    return PlainTextResponse(content=get_log_content())
