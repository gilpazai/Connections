from __future__ import annotations

from investigator.llm.prompts import THESIS_SYSTEM, make_user_prompt
from investigator.search.queries import QueryGenerator
from investigator.sections.base import BaseSection


class ThesisSection(BaseSection):
    def section_name(self) -> str:
        return "Thesis & Worldview"

    def generate_queries(self) -> list[str]:
        qg = QueryGenerator(self._config.name, self._config.company)
        return qg.thesis_queries()

    def get_system_prompt(self) -> str:
        return THESIS_SYSTEM

    def get_user_prompt(self, text: str) -> str:
        return make_user_prompt(self._config.name, self._config.company, text)
