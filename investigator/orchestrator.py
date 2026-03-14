from __future__ import annotations

import asyncio
import logging
import time

from investigator.cache.store import CacheStore
from investigator.config import InvestigatorConfig
from investigator.extraction.dedup import Deduplicator
from investigator.extraction.extractor import TextExtractor
from investigator.extraction.fetcher import PageFetcher
from investigator.llm.chunker import TextChunker
from investigator.llm.client import LLMClient, LLMError
from investigator.report.formatter import ReportFormatter
from investigator.report.writer import ReportWriter
from investigator.search.engine import SearchEngine
from investigator.sections.base import BaseSection, SectionResult
from investigator.sections.experience import ExperienceSection
from investigator.sections.posts import PostsSection
from investigator.sections.comments import CommentsSection
from investigator.sections.articles import ArticlesSection

logger = logging.getLogger(__name__)

SECTION_CLASSES: dict[str, type[BaseSection]] = {
    "experience": ExperienceSection,
    "posts": PostsSection,
    "comments": CommentsSection,
    "articles": ArticlesSection,
}


class Orchestrator:
    """Top-level coordinator: builds components, runs sections, assembles report."""

    async def _run_pipeline(self, config: InvestigatorConfig) -> list[SectionResult] | None:
        """Run the full search-fetch-synthesize pipeline, return section results."""
        logger.info("Person Investigation Agent v0.1.0")
        logger.info("Target: %s%s", config.name, f" ({config.company})" if config.company else "")

        # Shared infrastructure
        cache = CacheStore(
            cache_dir=".cache",
            ttl_hours=config.cache_ttl_hours,
            enabled=config.use_cache,
        )
        search_engine = SearchEngine(config, cache)
        fetcher = PageFetcher(config)
        extractor = TextExtractor()
        deduplicator = Deduplicator()
        chunker = TextChunker(config.llm_max_context_chars)

        # LLM probe
        llm = LLMClient(config)
        try:
            await llm.probe()
        except LLMError as exc:
            logger.error(str(exc))
            return None

        # Build section handlers
        section_kwargs = dict(
            config=config,
            search_engine=search_engine,
            fetcher=fetcher,
            extractor=extractor,
            deduplicator=deduplicator,
            llm=llm,
            chunker=chunker,
        )

        sections: list[BaseSection] = []
        for key in config.sections:
            cls = SECTION_CLASSES.get(key)
            if cls is None:
                logger.warning("Unknown section: %s", key)
                continue
            sections.append(cls(**section_kwargs))

        section_names = [s.section_name() for s in sections]

        if not sections:
            logger.error("No valid sections to run.")
            return None

        # Execute all sections concurrently
        logger.info("Starting investigation (%d sections)...", len(sections))
        start = time.time()

        raw_results = await asyncio.gather(
            *(s.execute() for s in sections),
            return_exceptions=True,
        )

        # Convert exceptions to error SectionResults
        results: list[SectionResult] = []
        for i, raw in enumerate(raw_results):
            if isinstance(raw, Exception):
                logger.error("Section '%s' failed: %s", section_names[i], raw)
                results.append(
                    SectionResult(
                        section_name=section_names[i],
                        markdown=f"*Section failed: {raw}*",
                        errors=[str(raw)],
                    )
                )
            else:
                results.append(raw)

        elapsed = time.time() - start
        logger.info("All sections complete in %.1f seconds.", elapsed)
        return results

    async def run(self, config: InvestigatorConfig) -> None:
        """Run pipeline and write report to disk (CLI entry point)."""
        results = await self._run_pipeline(config)
        if results is None:
            return

        formatter = ReportFormatter()
        report = formatter.format(config, results)

        writer = ReportWriter()
        writer.write(report, config.output_path)

    async def run_and_return(self, config: InvestigatorConfig) -> str:
        """Run pipeline and return the markdown report string (MCP entry point)."""
        results = await self._run_pipeline(config)
        if results is None:
            return "Error: no LLM backend available."

        formatter = ReportFormatter()
        return formatter.format(config, results)
