"""YAML Field Configuration Manager for progressive disclosure."""

import yaml
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from ..shared.exceptions import APIResponseError
from ..util.logging import get_logger

logger = get_logger(__name__)


# Default field configurations (DRY - single source of truth)
DEFAULT_MINIMAL_FIELDS = [
    "patentApplicationNumber",
    "publicationNumber",
    "groupArtUnitNumber",
    "citedDocumentIdentifier",
    "citationCategoryCode",
    "techCenter",
    "officeActionDate",
    "examinerCitedReferenceIndicator",
]

# MUST stay identical to predefined_sets.citations_balanced in
# field_configs.yaml, which is the set actually loaded; this list is only the
# no-YAML fallback. The two had drifted to 20 vs 19 members, and four of the
# extras (firstApplicantName, examinerNameText, decisionTypeCode,
# decisionTypeCodeDescriptionText) are fields the balanced tool's own
# docstring says do not exist on this API. Pinned by
# tests/test_field_counts.py (D-11).
DEFAULT_BALANCED_FIELDS = [
    "patentApplicationNumber",
    "publicationNumber",
    "groupArtUnitNumber",
    "citedDocumentIdentifier",
    "citationCategoryCode",
    "techCenter",
    "officeActionDate",
    "examinerCitedReferenceIndicator",
    "passageLocationText",
    "officeActionCategory",
    "relatedClaimNumberText",
    "nplIndicator",
    "workGroupNumber",
    "kindCode",
    "countryCode",
    "qualitySummaryText",
    "inventorNameText",
    "applicantCitedExaminerReferenceIndicator",
    "createDateTime",
]


def _check_not_in_sensitive_dir(abs_path: Path) -> None:
    """Raise ValueError if `abs_path` is within a system-sensitive directory
    (Windows and Unix). Extracted verbatim from _validate_config_path so the
    caller stays under the complexity threshold; behavior unchanged.
    """
    sensitive_dirs = [
        Path("/etc"),  # Unix system config
        Path("/sys"),  # Unix system files
        Path("/proc"),  # Unix process files
        Path("C:\\Windows"),  # Windows system
        Path("C:\\System32"),  # Windows system
        Path("/root"),  # Unix root home
        Path("/boot"),  # Unix boot files
    ]

    for sensitive_dir in sensitive_dirs:
        if not sensitive_dir.exists():
            continue
        try:
            abs_path.relative_to(sensitive_dir.resolve())
        except ValueError:
            # Not under this sensitive directory - this is good.
            continue
        # The raise MUST stay outside the try: relative_to signals "not under
        # this directory" with ValueError, so a deliberate raise inside the
        # try would be swallowed by its own except and the guard would never
        # fire.
        raise ValueError(f"Access to system directory denied: {sensitive_dir}")


class FieldManager:
    """
    Manages field configurations from YAML for progressive disclosure workflows.
    Supports runtime field selection without code changes.
    """

    def __init__(self, config_path: Path):
        # Path traversal protection
        validated_path = self._validate_config_path(config_path)
        self.config_path = validated_path
        self.config: Dict = {}
        self.load_config()

    def _validate_config_path(self, config_path: Path) -> Path:
        """
        Validate configuration file path to prevent path traversal attacks.

        Args:
            config_path: Path to validate

        Returns:
            Validated absolute path

        Raises:
            ValueError: If path is invalid or contains traversal attempts
        """
        try:
            # Convert to Path object if string
            if isinstance(config_path, str):
                config_path = Path(config_path)

            # Resolve to absolute path (resolves symlinks and relative paths)
            abs_path = config_path.resolve()

            # Get the project root (parent of src directory)
            project_root = Path(__file__).resolve().parent.parent.parent.parent

            # Security checks
            # 1. Prevent parent directory traversal
            if ".." in config_path.parts:
                raise ValueError(f"Path traversal detected: {config_path}")

            # 2. Ensure the resolved path is within the project directory. The
            #    process cwd is deliberately NOT an allowed root: under Docker
            #    it is /app, the whole application tree, which is not a
            #    meaningful boundary.
            try:
                abs_path.relative_to(project_root)
            except ValueError:
                raise ValueError(
                    f"Configuration file must be within the project directory. "
                    f"Path: {abs_path}, Project: {project_root}"
                )

            # 3. Prevent access to system-sensitive directories (Windows and Unix)
            _check_not_in_sensitive_dir(abs_path)

            # 4. Validate file extension (must be .yaml or .yml)
            if abs_path.suffix.lower() not in [".yaml", ".yml"]:
                raise ValueError(
                    f"Invalid file extension: {abs_path.suffix}. Must be .yaml or .yml"
                )

            logger.debug(f"Path validation passed: {abs_path}")
            return abs_path

        except ValueError:
            # The four checks above raise ValueError deliberately and their
            # messages name the rejected condition; let them through unwrapped.
            raise
        except (OSError, RuntimeError) as e:
            # Environment faults (permissions, symlink loops) are not the same
            # as a rejected path, but the caller can only act on one of them.
            logger.error(f"Path validation failed for {config_path}: {e}")
            raise ValueError(f"Invalid configuration path: {e}")

    def load_config(self):
        """Load and validate field configuration from YAML."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info(f"Field config loaded from {self.config_path}")
            else:
                logger.warning(
                    f"Config not found at {self.config_path}, using defaults"
                )
                self._set_default_config()
        except Exception as e:
            logger.error(f"Config loading failed: {e}. Using defaults.")
            self._set_default_config()

    def _set_default_config(self):
        """Fallback to default configuration if YAML missing or invalid."""
        self.config = {
            "predefined_sets": {
                "citations_minimal": {
                    "fields": list(DEFAULT_MINIMAL_FIELDS)  # Use module-level constant
                },
                "citations_balanced": {
                    "fields": list(DEFAULT_BALANCED_FIELDS)  # Use module-level constant
                },
            }
        }

    def get_field_set(self, set_name: str) -> List[str]:
        """Get the field-NAME list for a predefined set, from the local YAML.

        Named `get_field_set`, not `get_fields`: `BaseCitationClient.get_fields`
        returns the USPTO /fields catalog over the network and the two were
        used within three lines of each other, so a reader had to know which
        object was which to know whether a name list or an API catalog came
        back (R-3). `get_fields` remains as a thin alias for existing callers
        and tests (R-4).
        """
        sets = self.config.get("predefined_sets", {})
        field_set = sets.get(set_name, {})
        fields = field_set.get("fields", [])

        if not fields:
            logger.warning(f"No fields defined for set '{set_name}', using minimal")
            return self._get_default_minimal_fields()

        logger.debug(f"Fields for '{set_name}': {len(fields)} fields")
        return fields

    def get_fields(self, set_name: str) -> List[str]:
        """Alias for get_field_set. Kept for existing callers; prefer
        get_field_set, which says what it returns."""
        return self.get_field_set(set_name)

    def _get_default_minimal_fields(self) -> List[str]:
        """Get default minimal fields."""
        return list(DEFAULT_MINIMAL_FIELDS)  # Use module-level constant

    def filter_response(self, response: Dict, set_name: str) -> Dict:
        """
        Filter API response to include only specified fields.
        Maintains response structure: {"response": {"start": X, "numFound": Y, "docs": [...]}}
        """
        try:
            fields = self.get_field_set(set_name)
            if not fields:
                return response  # No filtering if no fields defined

            if "response" not in response or "docs" not in response["response"]:
                # Nothing to filter; the tier label cannot be over-claimed
                # because there are no documents in this payload.
                return response

            # Extract field set
            field_map = {f.lower(): f for f in fields}  # Case-insensitive matching

            filtered_docs = []
            for doc in response.get("response", {}).get("docs", []):
                filtered_doc = {}
                for key, value in doc.items():
                    # Match fields case-insensitively
                    lower_key = key.lower()
                    if lower_key in field_map:
                        filtered_doc[field_map[lower_key]] = value
                    # Always include core metadata if present
                    elif lower_key in ["id", "_version_", "score"]:
                        filtered_doc[key] = value
                filtered_docs.append(filtered_doc)

            # Preserve structure
            filtered_response = response.copy()
            filtered_response["response"]["docs"] = filtered_docs

            logger.debug(
                f"Filtered {len(response['response']['docs'])} docs to {len(filtered_docs)} fields"
            )
            return filtered_response

        except Exception:
            # Fail closed. Neither USPTO citations API honors `fl`, so this
            # method is the ONLY thing enforcing the advertised field tier;
            # returning the unfiltered upstream record here would make the
            # tier label a lie and over-disclose every field of every doc.
            logger.error("Response filtering failed for '%s'", set_name, exc_info=True)
            raise APIResponseError(
                "Could not apply the field tier to the upstream response",
                details={"field_set": set_name},
            )

    def validate_query_fields(self, query: str, field_set: str) -> Tuple[bool, str]:
        """Basic validation that query fields match available fields."""
        # This is a simple check - full Lucene validation in client
        allowed_fields = set(self.get_field_set(field_set))
        # Extract field names from query (basic parsing)
        potential_fields = re.findall(r"(\w+):", query)
        invalid_fields = [f for f in potential_fields if f not in allowed_fields]

        if invalid_fields:
            return (
                False,
                f"Invalid fields in query for '{field_set}': {', '.join(invalid_fields[:3])}",
            )

        return True, "Field validation passed"

    def validate_fields(self, field_list: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate a list of field names against available fields.

        Args:
            field_list: List of field names to validate

        Returns:
            Tuple of (is_valid, list of invalid field names)
        """
        all_available = self.get_all_available_fields()
        invalid = [f for f in field_list if f not in all_available]
        return (len(invalid) == 0, invalid)

    def get_all_available_fields(self) -> List[str]:
        """
        Get list of all available fields from predefined sets.

        Returns:
            List of all unique field names across all predefined sets
        """
        all_fields = set()
        sets = self.config.get("predefined_sets", {})
        for field_set in sets.values():
            fields = field_set.get("fields", [])
            all_fields.update(fields)
        # If no config loaded, return defaults
        if not all_fields:
            return list(DEFAULT_MINIMAL_FIELDS) + list(DEFAULT_BALANCED_FIELDS)
        return sorted(list(all_fields))

    def get_field_set_description(self, set_name: str) -> str:
        """
        Get description for a predefined field set.

        Args:
            set_name: Name of the field set

        Returns:
            Description string or empty string if not found
        """
        sets = self.config.get("predefined_sets", {})
        field_set = sets.get(set_name, {})
        return field_set.get("description", "")

    def filter_response_custom(
        self, response: Dict, custom_fields: List[str], include_id: bool = True
    ) -> Dict:
        """
        Filter API response to include only custom-specified fields.

        Eliminates duplication in main.py tool functions.

        Args:
            response: API response dict
            custom_fields: List of field names to include
            include_id: Whether to always include 'id' field (default: True)

        Returns:
            Filtered response with only specified fields
        """
        try:
            filtered = response.copy()

            if "response" not in filtered or "docs" not in filtered["response"]:
                return filtered

            filtered_docs = []
            for doc in filtered["response"]["docs"]:
                filtered_doc = {}

                # Include requested fields
                for field_name in custom_fields:
                    if field_name in doc:
                        filtered_doc[field_name] = doc[field_name]

                # Always include id if present (for tracking/debugging)
                if include_id and "id" in doc and "id" not in custom_fields:
                    filtered_doc["id"] = doc["id"]

                filtered_docs.append(filtered_doc)

            filtered["response"]["docs"] = filtered_docs

            logger.debug(
                f"Custom filtered {len(response['response']['docs'])} docs "
                f"to {len(custom_fields)} fields"
            )
            return filtered

        except Exception:
            # Fail closed, same reasoning as filter_response.
            logger.error("Custom response filtering failed", exc_info=True)
            raise APIResponseError(
                "Could not apply the requested field list to the upstream response",
                details={"field_count": len(custom_fields)},
            )

    def filter_response_smart(
        self,
        response: Dict,
        field_set_name: Optional[str] = None,
        custom_fields: Optional[List[str]] = None,
    ) -> Dict:
        """
        Smart filtering - use preset or custom fields.

        Unified method to eliminate duplication in tool functions.

        Args:
            response: API response dict
            field_set_name: Name of predefined field set (e.g., 'citations_minimal')
            custom_fields: List of custom field names (overrides field_set_name)

        Returns:
            Filtered response
        """
        if custom_fields is not None:
            return self.filter_response_custom(response, custom_fields)
        elif field_set_name is not None:
            return self.filter_response(response, field_set_name)
        else:
            # No filtering
            return response
