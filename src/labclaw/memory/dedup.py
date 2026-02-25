"""Pattern deduplication — prevents re-discovery of known patterns.

Implements the no-re-discovery requirement of C3 REMEMBER.

Match rule: same column_a + column_b + pattern_type → duplicate.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PatternDeduplicator:
    """Detects whether a new pattern duplicates a known one.

    Two patterns are considered duplicates when they share the same
    ``column_a``, ``column_b``, and ``pattern_type`` fields.
    If those fields are absent the patterns are never considered equal.
    """

    def __init__(self, known_patterns: list[dict[str, Any]]) -> None:
        self._known = list(known_patterns)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, new_pattern: dict[str, Any]) -> bool:
        """Return True if *new_pattern* matches any known pattern.

        Matching requires all three of column_a, column_b, pattern_type to
        be present and equal.  If any field is missing the pattern is treated
        as unique (no false positives).
        """
        col_a = new_pattern.get("column_a")
        col_b = new_pattern.get("column_b")
        ptype = new_pattern.get("pattern_type")

        if col_a is None or col_b is None or ptype is None:
            return False

        for known in self._known:
            if (
                known.get("column_a") == col_a
                and known.get("column_b") == col_b
                and known.get("pattern_type") == ptype
            ):
                return True

        return False

    def deduplicate(self, patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return *patterns* with duplicates removed.

        A pattern is removed if it matches any entry in ``_known`` OR if an
        earlier entry in *patterns* has already been seen (intra-list dedup).

        The relative order of unique patterns is preserved.
        """
        seen: list[dict[str, Any]] = list(self._known)
        result: list[dict[str, Any]] = []

        for pattern in patterns:
            col_a = pattern.get("column_a")
            col_b = pattern.get("column_b")
            ptype = pattern.get("pattern_type")

            is_dup = False
            if col_a is not None and col_b is not None and ptype is not None:
                for s in seen:
                    if (
                        s.get("column_a") == col_a
                        and s.get("column_b") == col_b
                        and s.get("pattern_type") == ptype
                    ):
                        is_dup = True
                        break

            if not is_dup:
                result.append(pattern)
                seen.append(pattern)
            else:
                logger.debug(
                    "Dedup: skipping known pattern (%s, %s, %s)", col_a, col_b, ptype
                )

        return result
