from __future__ import annotations

import asyncio
import logging

from investigator.config import InvestigatorConfig

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    """Unified LLM interface: OpenAI primary, Ollama secondary, Gemini fallback."""

    def __init__(self, config: InvestigatorConfig) -> None:
        self._config = config
        self._backend: str = "none"

    @property
    def backend(self) -> str:
        return self._backend

    async def probe(self) -> None:
        """Check which LLM backend is available, prioritizing selected provider."""
        provider = self._config.llm_provider

        if provider == "openai" or (not provider and self._config.openai_api_key):
            if not self._config.openai_api_key:
                raise LLMError("OpenAI selected but OPENAI_API_KEY is missing")
            self._backend = "openai"
            logger.info("LLM Backend: OpenAI (%s)", self._config.openai_model)
            return

        if provider == "anthropic" or (not provider and self._config.anthropic_api_key):
            if not self._config.anthropic_api_key:
                raise LLMError("Anthropic selected but ANTHROPIC_API_KEY is missing")
            self._backend = "anthropic"
            logger.info("LLM Backend: Anthropic (%s)", self._config.anthropic_model)
            return

        if provider == "gemini" or (not provider and self._config.gemini_api_key):
            if not self._config.gemini_api_key:
                raise LLMError("Gemini selected but GOOGLE_API_KEY is missing")
            self._backend = "gemini"
            logger.info("LLM Backend: Google Gemini (%s)", self._config.gemini_model)
            return

        if provider == "ollama" or (not provider and await self._probe_ollama()):
            if not await self._probe_ollama():
                raise LLMError("Ollama selected but not running or model missing")
            self._backend = "ollama"
            logger.info("LLM Backend: Ollama (%s)", self._config.model)
            return

        raise LLMError(
            "No LLM backend available. Please configure the LLM provider in settings."
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._backend == "openai":
            return await self._generate_openai(system_prompt, user_prompt)
        elif self._backend == "anthropic":
            return await self._generate_anthropic(system_prompt, user_prompt)
        elif self._backend == "ollama":
            return await self._generate_ollama(system_prompt, user_prompt)
        elif self._backend == "gemini":
            return await self._generate_gemini(system_prompt, user_prompt)
        raise LLMError("No LLM backend configured. Call probe() first.")

    # ── OpenAI ────────────────────────────────────────────────────────

    async def _generate_openai(self, system_prompt: str, user_prompt: str) -> str:
        import httpx

        def _call() -> str:
            payload = {
                "model": self._config.openai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
            }
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._config.openai_api_key}"},
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        return await asyncio.to_thread(_call)

    # ── Anthropic ───────────────────────────────────────────────────────

    async def _generate_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic

        def _call() -> str:
            client = anthropic.Anthropic(api_key=self._config.anthropic_api_key)
            response = client.messages.create(
                model=self._config.anthropic_model,
                max_tokens=4000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.content[0].text

        return await asyncio.to_thread(_call)

    # ── Ollama ────────────────────────────────────────────────────────

    async def _probe_ollama(self) -> bool:
        try:
            import ollama as _ollama

            def _check():
                response = _ollama.list()
                names = []
                # v0.6+: response is a Pydantic ListResponse with .models attribute
                model_list = getattr(response, "models", None)
                if model_list is None:
                    # Fallback for older dict-based API
                    model_list = response.get("models", []) if isinstance(response, dict) else []
                for m in model_list:
                    name = getattr(m, "model", "") or getattr(m, "name", "")
                    if not name and isinstance(m, dict):
                        name = m.get("model", "") or m.get("name", "")
                    if name:
                        names.append(name)
                return names

            names = await asyncio.to_thread(_check)
            target = self._config.model
            # Match "llama3.2" against "llama3.2:latest" etc.
            found = any(
                n == target or n.startswith(f"{target}:")
                for n in names
            )
            if not found:
                logger.warning(
                    "Ollama is running but model '%s' not found. "
                    "Available: %s. Attempting pull...",
                    target,
                    ", ".join(names) or "(none)",
                )
                try:
                    await asyncio.to_thread(_ollama.pull, target)
                    logger.info("Successfully pulled model '%s'", target)
                    found = True
                except Exception as pull_exc:
                    logger.warning("Could not pull model '%s': %s", target, pull_exc)
            return found
        except Exception as exc:
            logger.debug("Ollama not available: %s", exc)
            return False

    async def _generate_ollama(self, system_prompt: str, user_prompt: str) -> str:
        import ollama as _ollama

        def _call():
            resp = _ollama.chat(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={"temperature": 0.3},
            )
            # The library returns a Mapping or a ChatResponse object
            if hasattr(resp, 'message'):
                return resp.message.content
            if isinstance(resp, dict) and 'message' in resp:
                return resp['message']['content']
            return str(resp)

        return await asyncio.to_thread(_call)

    # ── Gemini ────────────────────────────────────────────────────────

    async def _generate_gemini(self, system_prompt: str, user_prompt: str) -> str:
        from google import genai

        client = genai.Client(api_key=self._config.gemini_api_key)

        def _call():
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=genai.types.GenerateContentConfig(
                    temperature=0.3,
                ),
            )
            return resp.text

        return await asyncio.to_thread(_call)
