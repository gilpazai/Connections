"""MCP server that exposes person-investigator as a tool over stdio."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from investigator.config import InvestigatorConfig
from investigator.orchestrator import Orchestrator

# Windows asyncio compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# All logging must go to stderr — stdout is the stdio transport channel
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP("person-investigator")


@mcp.tool()
async def investigate_person(
    name: str,
    company: str | None = None,
    sections: list[str] | None = None,
    model: str | None = None,
) -> str:
    """Investigate a person by searching public web sources and generating a markdown report.

    Args:
        name: Full name of the person to investigate.
        company: Optional company or organization the person is associated with.
        sections: Optional list of report sections to include.
                  Valid values: professional, expertise, content, social, news.
                  Defaults to all sections.
        model: LLM model name to use (e.g. "llama3.2", "gemini-2.0-flash").
               Defaults to INVESTIGATOR_MODEL env var or "llama3.2".
    """
    config = InvestigatorConfig(
        name=name,
        company=company,
        model=model or os.environ.get("INVESTIGATOR_MODEL", "llama3.2"),
        gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
        ollama_base_url=os.environ.get("INVESTIGATOR_OLLAMA_URL", "http://localhost:11434"),
        sections=sections or [],
    )

    logger.info("Starting investigation: %s", name)
    orchestrator = Orchestrator()
    report = await orchestrator.run_and_return(config)
    logger.info("Investigation complete: %s", name)
    return report


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
