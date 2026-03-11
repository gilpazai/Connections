from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Notion
    notion_token: str = ""
    notion_contacts_db_id: str = ""
    notion_leads_db_id: str = ""
    notion_work_history_db_id: str = ""
    notion_matches_db_id: str = ""

    # Google Gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # LLM provider for enrichment parsing: "gemini", "anthropic", or "ollama"
    llm_provider: str = "gemini"

    # Anthropic model
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # Ollama local LLM
    ollama_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://localhost:11434"

    # App behavior
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
