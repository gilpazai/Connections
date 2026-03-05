"""Rule registry for managing and discovering matching rules.

The registry is a simple list-based container. New rules are added by
implementing the MatchRule protocol and calling registry.register().
"""

from __future__ import annotations

from src.engine.rules.base import MatchRule
from src.engine.rules.shared_workplace import SharedWorkplaceRule


class RuleRegistry:
    """Container for registered matching rules."""

    def __init__(self) -> None:
        self._rules: list[MatchRule] = []

    def register(self, rule: MatchRule) -> None:
        """Register a new matching rule. Validates protocol conformance."""
        if not isinstance(rule, MatchRule):
            raise TypeError(
                f"{type(rule).__name__} does not implement the MatchRule protocol"
            )
        self._rules.append(rule)

    def get_all(self) -> list[MatchRule]:
        """Return all registered rules."""
        return list(self._rules)

    @property
    def rule_names(self) -> list[str]:
        return [r.name for r in self._rules]

    def __len__(self) -> int:
        return len(self._rules)


def create_default_registry() -> RuleRegistry:
    """Create a registry pre-loaded with all active matching rules."""
    registry = RuleRegistry()
    registry.register(SharedWorkplaceRule())
    return registry
