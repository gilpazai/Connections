from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InvestigatorConfig:
    name: str
    company: str | None = None
    model: str = "llama3.2"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    llm_provider: str | None = None
    output_path: str = ""
    use_cache: bool = True
    sections: list[str] = field(default_factory=list)
    verbose: bool = False

    # Tuning constants
    max_results_per_query: int = 8
    max_urls_per_section: int = 10
    fetch_timeout_seconds: int = 15
    rate_limit_delay: float = 1.5
    llm_max_context_chars: int = 12_000
    cache_ttl_hours: int = 24
    ollama_base_url: str = "http://localhost:11434"

    ALL_SECTIONS: list[str] = field(
        default_factory=lambda: [
            "experience",
            "posts",
            "comments",
            "articles",
        ],
        repr=False,
    )

    def __post_init__(self) -> None:
        import os
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.sections:
            self.sections = list(self.ALL_SECTIONS)
        if not self.output_path:
            safe_name = self.name.lower().replace(" ", "_")
            self.output_path = f"report_{safe_name}.md"
