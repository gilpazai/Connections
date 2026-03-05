"""Base protocol for matching rules.

All matching rules must implement the MatchRule protocol.
This is the extensibility contract: to add a new rule, create a class
that satisfies this protocol and register it in the RuleRegistry.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.engine.index import CompanyTimeIndex
from src.models.contact import WorkHistoryEntry
from src.models.match import Match


@runtime_checkable
class MatchRule(Protocol):
    """Protocol for all matching rules.

    Attributes:
        name: Short identifier for the rule (e.g. "SharedWorkplace").
        description: Human-readable explanation of what the rule detects.
    """

    name: str
    description: str

    def find_matches(
        self,
        contact_histories: dict[str, list[WorkHistoryEntry]],
        lead_histories: dict[str, list[WorkHistoryEntry]],
        index: CompanyTimeIndex,
    ) -> list[Match]:
        """Run this rule and return all discovered matches.

        Args:
            contact_histories: person_id -> work history entries for contacts
            lead_histories: person_id -> work history entries for leads
            index: Pre-built CompanyTimeIndex for efficient lookups

        Returns:
            List of Match objects found by this rule.
        """
        ...
