from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportWriter:
    """Writes the formatted report to file and console."""

    def write(self, content: str, output_path: str) -> None:
        path = Path(output_path)
        path.write_text(content, encoding="utf-8")
        logger.info("Report written to: %s", path.resolve())
        print(f"\n{'=' * 60}")
        print(content)
        print(f"{'=' * 60}\n")
