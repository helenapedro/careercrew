"""CareerCrew MCP server (Day 4 integration target).

Exposes the same document-access logic as the CrewAI @tool wrappers, but
over the Model Context Protocol: permission-scoped, auditable tools that any
MCP client can call, not just this crew.

Run standalone to test:
    python -m mcp_server.server
Day 4: connect the crew to this server and replace the @tool wrappers in
careercrew/tools.py with MCP-backed tools.
"""

from mcp.server.fastmcp import FastMCP

from careercrew.document_tools import fetch_job_description, read_resume

mcp = FastMCP("careercrew-docs")


@mcp.tool()
def read_resume_tool(path: str) -> str:
    """Read a resume file (PDF or TXT) from the uploads folder.

    The path is confined to the uploads folder; anything else is rejected.
    """
    return read_resume(path)


@mcp.tool()
def fetch_job_description_tool(source: str) -> str:
    """Get a job description from an https URL (timeout and size limits apply)
    or from pasted text."""
    return fetch_job_description(source)


if __name__ == "__main__":
    mcp.run()
