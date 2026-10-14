"""CrewAI tool wrappers (Day 2).

These wrap the shared logic in document_tools so the crew runs today.
Day 4 replaces these wrappers with MCP-backed tools served by
mcp_server/server.py; the underlying logic stays the same.
"""

from crewai.tools import tool

from careercrew.document_tools import fetch_job_description, read_resume


@tool("read_resume")
def read_resume_tool(path: str) -> str:
    """Read a resume file (PDF or TXT) from the uploads folder and return its
    text. Input is the file name, e.g. 'sample_resume.txt'."""
    return read_resume(path)


@tool("fetch_job_description")
def fetch_jd_tool(source: str) -> str:
    """Get a job description. Input is either an https URL (fetched with
    timeout and size limits) or the pasted JD text itself."""
    return fetch_job_description(source)
