import fitz
import re
from fastapi import HTTPException


def extract_text_from_pdf(file_bytes: bytes) -> str:

    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not open file. Make sure it is a valid PDF."
        )

    full_text = ""
    for page in pdf:
        full_text += page.get_text()

    pdf.close()

    full_text = re.sub(r"\s+", " ", full_text).strip()

    if not full_text:
        raise HTTPException(
            status_code=400,
            detail="PDF appears to be empty or contains no readable text."
        )

    return full_text