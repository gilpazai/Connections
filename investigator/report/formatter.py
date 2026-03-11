from __future__ import annotations

from datetime import datetime

from investigator.config import InvestigatorConfig
from investigator.sections.base import SectionResult


class ReportFormatter:
    """Assembles SectionResult objects into a complete Markdown report."""

    SECTION_ORDER = [
        "Professional Profile",
        "Expertise & Topics",
        "Recent Activity",
        "Thesis & Worldview",
        "Social Footprint",
    ]

    def format(
        self, config: InvestigatorConfig, results: list[SectionResult]
    ) -> str:
        by_name = {r.section_name: r for r in results}
        parts: list[str] = []

        # Header
        company_line = f"**Company:** {config.company}" if config.company else ""
        parts.append(
            f"# Investigation Report: {config.name}\n"
            f"{company_line}\n"
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"**Model:** {config.openai_model if config.openai_api_key else config.model}\n"
            f"\n---\n"
        )

        # Sections
        for i, name in enumerate(self.SECTION_ORDER, start=1):
            result = by_name.get(name)
            if result is None:
                continue

            markdown = result.markdown
            if name == "Social Footprint":
                lines = markdown.split('\n')
                table_lines = []
                in_list = False
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("- ") or stripped.startswith("* "):
                        if not in_list:
                            table_lines.extend(["| Platform | Details |", "|---|---|"])
                            in_list = True
                        content = stripped[2:].strip()
                        if ":" in content:
                            plat, rest = content.split(":", 1)
                            table_lines.append(f"| **{plat.strip()}** | {rest.strip()} |")
                        else:
                            table_lines.append(f"| | {content} |")
                    else:
                        in_list = False
                        table_lines.append(line)
                markdown = '\n'.join(table_lines)

            parts.append(f"## {i}. {name}\n")
            parts.append(markdown)

            if result.sources:
                parts.append("\n### Sources\n")
                for url in result.sources[:15]:
                    parts.append(f"- {url}")

            if result.errors:
                parts.append("\n> **Note:** Some data could not be retrieved:")
                for err in result.errors:
                    parts.append(f"> - {err}")

            parts.append("\n---\n")

        # Appendix
        parts.append("## Appendix: Data Collection Summary\n")
        parts.append(
            "| Section | Queries | Pages Fetched | After Dedup | Errors |"
        )
        parts.append(
            "|---------|---------|---------------|-------------|--------|"
        )
        for name in self.SECTION_ORDER:
            r = by_name.get(name)
            if r is None:
                continue
            parts.append(
                f"| {r.section_name} | {r.query_count} | {r.pages_fetched} "
                f"| {r.pages_after_dedup} | {len(r.errors)} |"
            )

        return "\n".join(parts)
