"""Local FastAPI entry point for the AutoApply CV parser service."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .extraction import ParsedCv, parse_file

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class ParseResponse(BaseModel):
    raw_text: str
    sections: list[dict[str, str | int | None]]
    tables: list[dict[str, object]]
    confidence: dict[str, object]


app = FastAPI(
    title="AutoApply CV Parser",
    version="0.1.0",
    description="Local document parsing API backed by Docling.",
)


def _suffix_for_upload(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, DOCX, and TXT files are accepted.",
        )
    return suffix


async def _save_upload(upload: UploadFile, suffix: str) -> Path:
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds 15 MB.")

    temporary = NamedTemporaryFile(prefix="autoapply-cv-", suffix=suffix, delete=False)
    try:
        temporary.write(content)
        return Path(temporary.name)
    finally:
        temporary.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse", response_model=ParseResponse)
async def parse(upload: UploadFile = File(...)) -> ParseResponse:
    """Parse one CV and remove the temporary upload regardless of outcome."""

    suffix = _suffix_for_upload(upload)
    temp_path = await _save_upload(upload, suffix)
    try:
        parsed: ParsedCv = parse_file(temp_path, suffix)
        return ParseResponse(**parsed.model_dump())
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - protects the API boundary
        raise HTTPException(status_code=500, detail="Document parsing failed.") from error
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
