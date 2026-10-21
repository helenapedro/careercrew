"""Real MCP client/server round-trip tests (no LLM key needed)."""

from __future__ import annotations

from careercrew.mcp_client import (
    EXPECTED_TOOLS,
    MCPToolClient,
    mcp_read_job_description,
    mcp_read_resume,
)


async def test_server_exposes_expected_tools():
    client = MCPToolClient()
    async with client.session() as session:
        names = await client.list_tool_names(session=session)
    assert EXPECTED_TOOLS.issubset(set(names))
    assert "read_job_description_tool" in names


def test_mcp_read_resume_round_trip(upload_dir):
    (upload_dir / "resume.txt").write_text("JANE DOE Python AWS", encoding="utf-8")
    text = mcp_read_resume("resume.txt")
    assert "JANE DOE" in text


def test_mcp_read_job_description_round_trip(upload_dir):
    (upload_dir / "posting.txt").write_text("Need FastAPI and AWS.", encoding="utf-8")
    text = mcp_read_job_description("posting.txt")
    assert "FastAPI" in text
