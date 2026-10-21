"""Tests for document_tools: resume and JD input (file or pasted text)."""

from __future__ import annotations

import pytest

from careercrew.document_tools import (
    JobDescriptionError,
    read_job_description,
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
    """PDF parsing path uses pypdf; a blank page yields empty text (no crash)."""
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = upload_dir / "resume.pdf"
    with open(path, "wb") as handle:
        writer.write(handle)
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


# --------------------------------------------------------------------------- #
# Job description: pasted text or uploaded file
# --------------------------------------------------------------------------- #
def test_read_jd_pasted_text():
    assert read_job_description("We need a Python engineer.") == "We need a Python engineer."


def test_read_jd_rejects_empty():
    with pytest.raises(JobDescriptionError):
        read_job_description("   ")


def test_read_jd_rejects_url():
    """URLs are no longer read directly; the user is told to upload or paste."""
    with pytest.raises(JobDescriptionError, match="not read directly"):
        read_job_description("https://www.linkedin.com/jobs/view/1234567890/")


def test_read_jd_from_txt_file(upload_dir):
    name = _write(upload_dir / "posting.txt", "Need FastAPI and AWS skills.")
    text = read_job_description(name)
    assert "FastAPI" in text


def test_read_jd_from_docx_file(upload_dir):
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Senior Backend Engineer")
    document.add_paragraph("Required: PostgreSQL, Docker")
    path = upload_dir / "posting.docx"
    document.save(str(path))
    text = read_job_description("posting.docx")
    assert "PostgreSQL" in text


def test_read_jd_filename_without_upload_treated_as_text(upload_dir):
    """A bare *.txt name that is not actually uploaded is treated as pasted text."""
    assert read_job_description("posting.txt") == "posting.txt"


def test_read_resume_file_redacts_pii(upload_dir):
    name = _write(
        upload_dir / "resume.txt",
        "JANE DOE\njane.doe@example.com\n+1 (555) 123-4567\nPython AWS",
    )
    text = read_resume(name)
    assert "jane.doe@example.com" not in text
    assert "555" not in text
    assert "[redacted email]" in text
    assert "[redacted phone]" in text
    assert "JANE DOE" in text  # names pass through
    assert "Python" in text


def test_read_jd_file_redacts_pii(upload_dir):
    name = _write(
        upload_dir / "jd.txt",
        "Python role. Contact hr@company.com or +1-555-987-6543 for details.",
    )
    text = read_job_description(name)
    assert "hr@company.com" not in text
    assert "[redacted email]" in text
    assert "[redacted phone]" in text
    assert "Python role" in text
