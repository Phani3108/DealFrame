"""LangChain tool for TemporalOS.

Exposes TemporalOS video Q&A and job search as a LangChain BaseTool so it
can be dropped into any LangChain agent or chain.

Usage:
    from temporalos.integrations.langchain_tool import TemporalOSTool
    tool = TemporalOSTool(base_url="http://localhost:8000", api_key="...")
    # Use in any LangChain AgentExecutor
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class TemporalOSTool:
    """LangChain-compatible tool that queries TemporalOS API.

    If `langchain_core` is installed, inherits from BaseTool automatically
    using a lazy registration pattern so the package remains optional.
    """

    name: str = "temporalos_search"
    description: str = (
        "Search and query a TemporalOS video intelligence library. "
        "Input: a natural-language question about video content, meeting analysis, "
        "objections, risk scores, or decision signals. "
        "Returns a structured answer with source citations."
    )

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    # ------------------------------------------------------------------
    # Core logic (always available)
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        from temporalos.integrations.base import http_get
        status, resp = http_get(
            f"{self.base_url}/api/v1/search",
            params={"q": query, "limit": str(top_k)},
            headers=self._headers(),
        )
        return resp

    def ask(self, question: str) -> str:
        """Call the Q&A agent endpoint. Returns plain-text answer with citations."""
        from temporalos.integrations.base import http_get
        status, resp = http_get(
            f"{self.base_url}/api/v1/agents/qa",
            params={"q": question},
            headers=self._headers(),
        )
        if status != 200:
            return f"Error {status}: {resp.get('detail', 'unknown error')}"
        return resp.get("answer", "") + "\n\nSources: " + ", ".join(
            c.get("job_id", "?") for c in resp.get("citations", [])
        )

    def run(self, tool_input: str) -> str:  # BaseTool.run signature
        return self.ask(tool_input)

    def _run(self, query: str) -> str:  # BaseTool._run signature
        return self.run(query)

    async def _arun(self, query: str) -> str:
        return self._run(query)

    # ------------------------------------------------------------------
    # LangChain integration (optional)
    # ------------------------------------------------------------------

    @classmethod
    def as_langchain_tool(cls, base_url: str = "http://localhost:8000",
                          api_key: str = "") -> "TemporalOSTool":
        """Return self as a proper LangChain BaseTool if langchain_core is installed."""
        try:
            from langchain_core.tools import BaseTool

            class _LCTool(BaseTool, cls):  # type: ignore[misc]
                name: str = "temporalos_search"
                description: str = cls.description

                def _run(self, query: str) -> str:
                    return super()._run(query)

                async def _arun(self, query: str) -> str:
                    return super()._run(query)

            return _LCTool(base_url=base_url, api_key=api_key)
        except ImportError:
            logger.info("langchain_core not installed; returning plain TemporalOSTool")
            return cls(base_url=base_url, api_key=api_key)
