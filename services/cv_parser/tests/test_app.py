from __future__ import annotations

from fastapi.testclient import TestClient

from services.cv_parser import app as app_module
from services.cv_parser.extraction import ParsedCv, split_markdown_sections


client = TestClient(app_module.app)


def test_split_markdown_sections_preserves_heading_metadata() -> None:
    sections = split_markdown_sections("# Profile\n\nA short profile.\n\n## Skills\n\nPython")
    assert sections == [
        {"title": "Profile", "level": 1, "content": "A short profile."},
        {"title": "Skills", "level": 2, "content": "Python"},
    ]


def test_parse_rejects_unsupported_file_type() -> None:
    response = client.post("/parse", files={"upload": ("cv.exe", b"data", "application/octet-stream")})
    assert response.status_code == 415


def test_parse_removes_temporary_upload_after_success(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_parse_file(path, suffix):
        recorded["path"] = path
        recorded["suffix"] = suffix
        return ParsedCv(
            raw_text="Hasan Adam",
            sections=[{"title": None, "level": None, "content": "Hasan Adam"}],
            tables=[],
            confidence={"source": "test"},
        )

    monkeypatch.setattr(app_module, "parse_file", fake_parse_file)
    response = client.post("/parse", files={"upload": ("cv.txt", b"Hasan Adam", "text/plain")})

    assert response.status_code == 200
    assert response.json()["raw_text"] == "Hasan Adam"
    assert recorded["suffix"] == ".txt"
    assert not recorded["path"].exists()
