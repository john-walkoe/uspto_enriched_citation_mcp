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


class BackupPolicy(Enum):
    """
    Backup policy for destructive operations.

    Replaces `backup: bool` parameter with descriptive options.
    """

    CREATE_BACKUP = "create_backup"  # Create backup before operation
    NO_BACKUP = "no_backup"  # Skip backup (faster but riskier)
    AUTO = "auto"  # Automatic decision based on config

    def __bool__(self) -> bool:
        """
        Allow enum to be used in boolean context for backward compatibility.

        Returns:
            True for CREATE_BACKUP/AUTO, False for NO_BACKUP
        """
        return self in (BackupPolicy.CREATE_BACKUP, BackupPolicy.AUTO)

    @classmethod
    def from_bool(cls, value: bool) -> "BackupPolicy":
        """
        Convert boolean to BackupPolicy for backward compatibility.

        Args:
            value: Boolean value (True = CREATE_BACKUP, False = NO_BACKUP)

        Returns:
            Corresponding BackupPolicy
        """
        return cls.CREATE_BACKUP if value else cls.NO_BACKUP


class SearchMode(Enum):
    """
    Search result detail level.

    Future use for controlling search verbosity.
    """

    ULTRA_MINIMAL = "ultra_minimal"  # Absolute minimum fields (custom selection)
    MINIMAL = "minimal"  # Essential fields only (preset)
    BALANCED = "balanced"  # Moderate detail (preset)
    COMPREHENSIVE = "comprehensive"  # All available fields


class ValidationLevel(Enum):
    """
    Input validation strictness level.

    Future use for controlling validation behavior.
    """

    STRICT = "strict"  # Enforce all validation rules
    LENIENT = "lenient"  # Allow some flexibility
    DISABLED = "disabled"  # Skip validation (not recommended)
