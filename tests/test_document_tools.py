"""Tests for document_tools: resume file/paste input and JD URL handling."""

from __future__ import annotations

import pytest

from careercrew.document_tools import (
    JobDescriptionError,
    fetch_job_description,
    read_resume,
    read_resume_text,
)


def _write(path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return path.name


def test_read_txt_resume(upload_dir):
    name = _write(upload_dir / "resume.txt", "JANE DOE  Python  AWS")
    text = read_resume(name)
    assert "JANE DOE" in text
    assert "Python" in text


def test_read_docx_resume(upload_dir):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("JANE DOE")
    document.add_paragraph("Skills: Python, AWS")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "2020"
    table.cell(0, 1).text = "Engineer"
    path = upload_dir / "resume.docx"
    document.save(str(path))

    text = read_resume("resume.docx")
    assert "JANE DOE" in text
    assert "Engineer" in text


def test_read_pdf_resume(upload_dir):
    """PDF parsing path uses pypdf; we assert it does not raise on a real PDF.

    pypdf cannot easily write text PDFs, so we only exercise the extension
    routing by expecting a handled error or text for an empty PDF.
    """
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = upload_dir / "resume.pdf"
    with open(path, "wb") as handle:
        writer.write(handle)
    # A blank page yields empty text, which is valid behaviour (no crash).
    assert read_resume("resume.pdf") == ""


def test_read_resume_rejects_path_traversal(upload_dir):
    with pytest.raises(ValueError):
        read_resume("../secrets.txt")


def test_read_resume_missing_file(upload_dir):
    with pytest.raises(FileNotFoundError):
        read_resume("nope.txt")


def test_read_resume_text_normalizes_whitespace():
    text = read_resume_text("  JANE   DOE \n\n Python  ")
    assert text == "JANE DOE Python"


def test_read_resume_text_rejects_empty():
    with pytest.raises(ValueError):
        read_resume_text("   ")


def test_fetch_job_description_pasted_text():
    assert fetch_job_description("We need a Python engineer.") == "We need a Python engineer."


def test_fetch_job_description_rejects_empty():
    with pytest.raises(JobDescriptionError):
        fetch_job_description("   ")


def test_fetch_job_description_rejects_non_https_url():
    with pytest.raises(JobDescriptionError):
        fetch_job_description("http://insecure.example.com/job")


def test_fetch_job_description_rejects_linkedin_url():
    with pytest.raises(JobDescriptionError, match="blocks automated access"):
        fetch_job_description("https://www.linkedin.com/jobs/view/1234567890/")


def test_fetch_job_description_unreachable_url(monkeypatch):
    import urllib.error

    from careercrew import document_tools

    def _boom(*args, **kwargs):
        raise urllib.error.URLError("name resolution failed")

    monkeypatch.setattr(document_tools.urllib.request, "urlopen", _boom)
    with pytest.raises(JobDescriptionError, match="could not be reached"):
        fetch_job_description("https://nonexistent.invalid/job")


def test_fetch_job_description_http_error(monkeypatch):
    import urllib.error

    from careercrew import document_tools

    def _boom(*args, **kwargs):
        raise urllib.error.HTTPError("https://x/y", 403, "Forbidden", {}, None)

    monkeypatch.setattr(document_tools.urllib.request, "urlopen", _boom)
    with pytest.raises(JobDescriptionError, match="403"):
        fetch_job_description("https://blocked.example.com/job")


class _FakeResponse:
    def __init__(self, body: bytes, content_type: str):
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self, _n: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_job_description_rejects_non_html(monkeypatch):
    from careercrew import document_tools

    monkeypatch.setattr(
        document_tools.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(b"%PDF-1.4", "application/pdf"),
    )
    with pytest.raises(JobDescriptionError, match="cannot be read"):
        fetch_job_description("https://cdn.example.com/job.pdf")


def test_fetch_job_description_parses_html(monkeypatch):
    from careercrew import document_tools

    html = b"<html><body><h1>Job</h1><script>x()</script><p>Need Python</p></body></html>"
    monkeypatch.setattr(
        document_tools.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(html, "text/html; charset=utf-8"),
    )
    text = fetch_job_description("https://jobs.example.com/role")
    assert "Need Python" in text
    assert "x()" not in text
