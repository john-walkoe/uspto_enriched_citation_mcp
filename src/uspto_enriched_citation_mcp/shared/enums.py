"""Common enums for type-safe parameter passing.

Replaces boolean parameters with descriptive enums for better code clarity
and maintainability.
"""

from enum import Enum


class ContextLevel(Enum):
    """
    Citation context inclusion level.

    Replaces `include_context: bool` parameter with descriptive options.
    """

    MINIMAL = "minimal"  # Basic citation data only (no context)
    FULL = "full"  # Complete citation with all available context
    BALANCED = "balanced"  # Moderate detail (future use)

    def __bool__(self) -> bool:
        """
        Allow enum to be used in boolean context for backward compatibility.

        Returns:
            True for FULL/BALANCED, False for MINIMAL
        """
        return self in (ContextLevel.FULL, ContextLevel.BALANCED)

    @classmethod
    def from_bool(cls, value: bool) -> "ContextLevel":
        """
        Convert boolean to ContextLevel for backward compatibility.

        Args:
            value: Boolean value (True = FULL, False = MINIMAL)

        Returns:
            Corresponding ContextLevel
        """
        return cls.FULL if value else cls.MINIMAL
