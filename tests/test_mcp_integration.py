"""Real MCP client/server round-trip tests (no LLM key needed)."""

from __future__ import annotations

from careercrew.mcp_client import (
    EXPECTED_TOOLS,
    MCPToolClient,
    mcp_query_answer_bank,
    mcp_read_resume,
)


async def test_server_exposes_expected_tools():
    client = MCPToolClient()
    async with client.session() as session:
        names = await client.list_tool_names(session=session)
    assert EXPECTED_TOOLS.issubset(set(names))


async def test_answer_bank_over_mcp():
    client = MCPToolClient()
    async with client.session() as session:
        result = await client.call_tool_async(
            "query_answer_bank_tool",
            {"question": "What is your notice period?"},
            session=session,
        )
    assert result["found"] is True
    assert result["source"] == "answer_bank"


def test_mcp_read_resume_round_trip(upload_dir):
    (upload_dir / "resume.txt").write_text("JANE DOE Python AWS", encoding="utf-8")
    text = mcp_read_resume("resume.txt")
    assert "JANE DOE" in text


def test_mcp_query_answer_bank_one_shot():
    assert mcp_query_answer_bank("Are you willing to relocate?")["found"] is True
