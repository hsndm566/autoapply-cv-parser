# AutoApply CV Parser

This local FastAPI service accepts a single CV upload and returns normalized text, headings, tables, and Docling confidence metadata. It accepts **PDF**, **DOCX**, and **TXT** files only. Uploads are written to a unique temporary path and deleted in a `finally` block after each request, including failed parsing attempts.

## Local setup

Use Python 3.10 or later. From the repository root, install the forked Docling package and the small service dependency set:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r services/cv_parser/requirements.txt
```

Run the local API:

```bash
uvicorn services.cv_parser.app:app --reload --port 8000
```

## Endpoint usage

```bash
curl -X POST http://127.0.0.1:8000/parse \
  -F "upload=@/absolute/path/to/cv.pdf"
```

The response shape is:

```json
{
  "raw_text": "...",
  "sections": [{"title": "Experience", "level": 2, "content": "..."}],
  "tables": [{"index": 0, "columns": ["Skill"], "rows": [["Python"]]}],
  "confidence": {"source": "docling", "report": {}}
}
```

## Tests

```bash
pytest -q services/cv_parser/tests
```

The unit tests mock the expensive conversion layer and verify input validation, stable section handling, and temporary-upload deletion. A real PDF/DOCX smoke test may download or initialize Docling model artifacts, so it is intentionally not part of the lightweight test command.

## Deployment notes

This repository is **not deployed**. A future deployment should run the service behind authenticated HTTPS, enforce request-size and file-type policy at the edge, and use ephemeral or encrypted storage only. Do not persist original CV uploads or parsed candidate text by default.
