from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from investigator.config import InvestigatorConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="investigator",
        description=(
            "Person Investigation Agent — generates a comprehensive report "
            "about a person using public web sources and LLM synthesis."
        ),
    )
    parser.add_argument("name", help="Full name of the person to investigate")
    parser.add_argument(
        "--company", default=None, help="Company or organization affiliation"
    )
    parser.add_argument(
        "--model", default="llama3.2", help="Ollama model name (default: llama3.2)"
    )
    parser.add_argument(
        "--gemini-key", default=None, dest="gemini_key", help="Google Gemini API key for LLM fallback"
    )
    import os
    parser.add_argument(
        "--openai-key", default=os.environ.get("OPENAI_API_KEY"), dest="openai_key", help="OpenAI API key"
    )
    parser.add_argument(
        "--output", default="", help="Output file path (default: report_{name}.md)"
    )
    parser.add_argument(
        "--no-cache", action="store_true", dest="no_cache", help="Disable result caching"
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        default=[],
        choices=["experience", "posts", "comments", "articles"],
        help="Run only specific sections",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
    )

    config = InvestigatorConfig(
        name=args.name,
        company=args.company,
        model=args.model,
        gemini_api_key=args.gemini_key,
        openai_api_key=args.openai_key,
        output_path=args.output,
        use_cache=not args.no_cache,
        sections=args.sections,
        verbose=args.verbose,
    )

    from investigator.orchestrator import Orchestrator

    orchestrator = Orchestrator()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(orchestrator.run(config))
