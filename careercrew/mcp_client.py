"""CareerCrew - real MCP client.

This module speaks the actual Model Context Protocol over the official ``mcp``
Python SDK. It is used in two ways:

1. :class:`MCPToolClient` opens a stdio session to :mod:`mcp_server.server`,
   lists the tools, and calls them. This is what the tests exercise to prove a
   real client/server round trip, and what the deterministic pipeline fallback
   uses.
2. :func:`crewai_mcp_server` returns a CrewAI ``MCPServerStdio`` configuration so
   the agents can call the same tools natively through CrewAI.

Both paths hit the *same* server, so no matter which one an agent uses, the call
is a genuine MCP call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from careercrew.config import PROJECT_ROOT

logger = logging.getLogger("careercrew.mcp_client")

#: Tools exposed by our server that we expect to exist.
EXPECTED_TOOLS = {"read_resume_tool", "fetch_job_description_tool", "query_answer_bank_tool"}


def _server_env() -> dict[str, str]:
    """Environment for the MCP server subprocess.

    The MCP SDK only forwards a safe allowlist of variables by default, which
    would drop ``CAREERCREW_UPLOAD_DIR`` / ``CAREERCREW_DB_PATH``. We pass the
    full environment so the server resolves the same folders as the app.
    """
    return dict(os.environ)


def server_params() -> StdioServerParameters:
    """Build stdio launch parameters for the CareerCrew MCP server.

    Uses the current interpreter so the server runs inside the same virtual
    environment (and therefore has the project dependencies available).
    """
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=_server_env(),
        cwd=str(PROJECT_ROOT),
    )


def crewai_mcp_server(*, cache_tools: bool = True):
    """Return a CrewAI ``MCPServerStdio`` config bound to our MCP server.

    Imported lazily so that this module can be used (and tested) even when
    CrewAI is not the caller.
    """
    from crewai.mcp import MCPServerStdio

    return MCPServerStdio(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=_server_env(),
        cache_tools_list=cache_tools,
    )


def _decode_tool_result(result: Any) -> Any:
    """Decode an MCP CallToolResult into plain Python data.

    FastMCP returns structured content; fall back to parsing the text block as
    JSON when structured content is absent. Scalar (str) tool returns arrive
    wrapped as ``{"result": value}``, which we unwrap so callers get the value.
    """
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return _unwrap_result(structured)

    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            try:
                return _unwrap_result(json.loads(text))
            except (ValueError, TypeError):
                return text
    return None


def _unwrap_result(value: Any) -> Any:
    """Unwrap the ``{"result": ...}`` envelope FastMCP adds for scalar returns."""
    if isinstance(value, dict) and set(value.keys()) == {"result"}:
        return value["result"]
    return value


class MCPToolClient:
    """A synchronous-friendly wrapper over a stdio MCP session.

    Call :meth:`session` as an async context manager, then use the async helpers
    from async code or the blocking helpers from synchronous code.
    """

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._timeout_s = timeout_s
        self._session: ClientSession | None = None

    # -- async context manager -------------------------------------------------
    @asynccontextmanager
    async def session(self):
        """Open a stdio session to the MCP server."""
        async with stdio_client(server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self._timeout_s)
                self._session = session
                try:
                    yield session
                finally:
                    self._session = None

    # -- async operations ------------------------------------------------------
    async def list_tool_names(self, session: ClientSession | None = None) -> list[str]:
        """Return the names of tools the server exposes."""
        sess = session or self._session
        if sess is None:
            raise RuntimeError("MCP session is not open")
        result = await asyncio.wait_for(sess.list_tools(), timeout=self._timeout_s)
        return [tool.name for tool in result.tools]

    async def call_tool_async(
        self, name: str, arguments: dict[str, Any], session: ClientSession | None = None
    ) -> Any:
        """Call a tool asynchronously and decode the result."""
        sess = session or self._session
        if sess is None:
            raise RuntimeError("MCP session is not open")
        result = await asyncio.wait_for(
            sess.call_tool(name, arguments), timeout=self._timeout_s
        )
        if getattr(result, "isError", False):
            raise RuntimeError(f"MCP tool {name} returned an error")
        return _decode_tool_result(result)

    # -- synchronous operations ------------------------------------------------
    def read_resume(self, path: str) -> str:
        """Call ``read_resume_tool`` and return the resume text."""
        return _run(self._call("read_resume_tool", {"path": path}))

    def fetch_job_description(self, source: str) -> str:
        """Call ``fetch_job_description_tool`` and return the JD text."""
        return _run(self._call("fetch_job_description_tool", {"source": source}))

    def query_answer_bank(self, question: str) -> dict[str, Any]:
        """Call ``query_answer_bank_tool`` and return the decoded payload."""
        return _run(self._call("query_answer_bank_tool", {"question": question}))

    async def _call(self, name: str, arguments: dict[str, Any]) -> Any:
        async with self.session() as session:
            return await self.call_tool_async(name, arguments, session=session)


def _run(coro):
    """Run an async coroutine to completion from synchronous code.

    Uses a dedicated event loop so this is safe to call from within Gradio
    worker threads as well as from plain scripts.
    """
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --------------------------------------------------------------------------- #
# Convenience: one-shot real MCP calls
# --------------------------------------------------------------------------- #
def mcp_read_resume(path: str) -> str:
    """Perform a real MCP ``read_resume_tool`` call in one shot."""
    return MCPToolClient().read_resume(path)


def mcp_fetch_job_description(source: str) -> str:
    """Perform a real MCP ``fetch_job_description_tool`` call in one shot."""
    return MCPToolClient().fetch_job_description(source)


def mcp_query_answer_bank(question: str) -> dict[str, Any]:
    """Perform a real MCP ``query_answer_bank_tool`` call in one shot."""
    return MCPToolClient().query_answer_bank(question)
