"""CrewAI @tool wrappers (optional, local fallback).

The crew's agents are wired to the **real** MCP server (see
``careercrew/mcp_client.py`` and ``careercrew/crew.py``). These plain CrewAI
tools wrap the same shared logic in ``document_tools`` and are kept as a local
alternative / for tests; the underlying logic is identical either way.
"""

from crewai.tools import tool

from careercrew.document_tools import (
    query_answer_bank,
    read_job_description,
    read_resume,
)


@tool("read_resume")
def read_resume_tool(path: str) -> str:
    """Read a resume file (PDF, DOCX, or TXT) from the uploads folder and return
    its text. Input is the file name, e.g. 'sample_resume.txt'."""
    return read_resume(path)


@tool("read_job_description")
def read_jd_tool(source: str) -> str:
    """Get a job description. Input is either the uploaded JD file name
    (PDF, DOCX, or TXT) or the pasted JD text itself."""
    return read_job_description(source)


@tool("query_answer_bank")
def query_answer_bank_tool(question: str) -> dict:
    """Look up a verified answer to an employer screening question. Returns a
    verified answer (source=answer_bank) or found=false when none exists."""
    return query_answer_bank(question)
