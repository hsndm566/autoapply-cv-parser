"""Docling result normalization for the AutoApply CV parser service."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ParsedCv(BaseModel):
    raw_text: str
    sections: list[dict[str, str | int | None]]
    tables: list[dict[str, object]]
    confidence: dict[str, object]


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def split_markdown_sections(markdown: str) -> list[dict[str, str | int | None]]:
    """Turn Docling markdown into a stable, API-friendly section list."""

    sections: list[dict[str, str | int | None]] = []
    title: str | None = None
    level: int | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal lines
        content = "\n".join(lines).strip()
        if content or title:
            sections.append({"title": title, "level": level, "content": content})
        lines = []

    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
        else:
            lines.append(line)
    flush()

    return sections or [{"title": None, "level": None, "content": markdown.strip()}]


def _raw_text(document: Any, markdown: str) -> str:
    texts = [str(item.text).strip() for item in getattr(document, "texts", []) if getattr(item, "text", None)]
    return "\n".join(texts).strip() or markdown.strip()


def _tables(document: Any) -> list[dict[str, object]]:
    tables: list[dict[str, object]] = []
    for index, table in enumerate(getattr(document, "tables", [])):
        item: dict[str, object] = {"index": index}
        try:
            dataframe = table.export_to_dataframe()
            item["columns"] = [str(column) for column in dataframe.columns.tolist()]
            item["rows"] = dataframe.fillna("").astype(str).values.tolist()
        except Exception:
            item["markdown"] = str(table)
        tables.append(item)
    return tables


def _confidence(result: Any, source: str) -> dict[str, object]:
    confidence = getattr(result, "confidence", None)
    if confidence is None:
        return {"source": source, "status": "not_available"}
    if hasattr(confidence, "model_dump"):
        return {"source": source, "report": confidence.model_dump(mode="json")}
    return {"source": source, "report": str(confidence)}


def parse_file(path: Path, suffix: str) -> ParsedCv:
    """Parse a temporary file with Docling, or safely normalize a TXT upload."""

    if suffix == ".txt":
        raw_text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw_text:
            raise ValueError("No readable text was found in the uploaded TXT file.")
        return ParsedCv(
            raw_text=raw_text,
            sections=split_markdown_sections(raw_text),
            tables=[],
            confidence={"source": "plain_text", "status": "not_applicable"},
        )

    # Import lazily so local unit tests can validate HTTP and cleanup behavior
    # without downloading or loading document-model artifacts.
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter

    input_format = InputFormat.PDF if suffix == ".pdf" else InputFormat.DOCX
    converter = DocumentConverter(allowed_formats=[input_format])
    result = converter.convert(path)
    markdown = result.document.export_to_markdown()
    raw_text = _raw_text(result.document, markdown)
    if not raw_text:
        raise ValueError("Docling did not return readable text for this document.")

    return ParsedCv(
        raw_text=raw_text,
        sections=split_markdown_sections(markdown),
        tables=_tables(result.document),
        confidence=_confidence(result, "docling"),
    )
