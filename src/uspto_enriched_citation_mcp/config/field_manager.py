"""YAML Field Configuration Manager for progressive disclosure."""

import yaml
import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


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
    "firstApplicantName",
    "examinerNameText",
    "decisionTypeCode",
    "decisionTypeCodeDescriptionText",
]


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

            # 2. Ensure the resolved path is within project directory or current working directory
            cwd = Path.cwd().resolve()
            is_in_project = False
            try:
                abs_path.relative_to(project_root)
                is_in_project = True
            except ValueError:
                pass

            is_in_cwd = False
            try:
                abs_path.relative_to(cwd)
                is_in_cwd = True
            except ValueError:
                pass

            if not (is_in_project or is_in_cwd):
                raise ValueError(
                    f"Configuration file must be within project directory or current working directory. "
                    f"Path: {abs_path}, Project: {project_root}, CWD: {cwd}"
                )

            # 3. Prevent access to system-sensitive directories (Windows and Unix)
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
                if sensitive_dir.exists():
                    try:
                        abs_path.relative_to(sensitive_dir.resolve())
                        raise ValueError(
                            f"Access to system directory denied: {sensitive_dir}"
                        )
                    except ValueError:
                        # Not under sensitive directory - this is good
                        pass

            # 4. Validate file extension (must be .yaml or .yml)
            if abs_path.suffix.lower() not in [".yaml", ".yml", ""]:
                raise ValueError(
                    f"Invalid file extension: {abs_path.suffix}. Must be .yaml or .yml"
                )

            logger.debug(f"Path validation passed: {abs_path}")
            return abs_path

        except Exception as e:
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

    def get_fields(self, set_name: str) -> List[str]:
        """Get field list for predefined set."""
        sets = self.config.get("predefined_sets", {})
        field_set = sets.get(set_name, {})
        fields = field_set.get("fields", [])

        if not fields:
            logger.warning(f"No fields defined for set '{set_name}', using minimal")
            return self._get_default_minimal_fields()

        logger.debug(f"Fields for '{set_name}': {len(fields)} fields")
        return fields

    def get_field_set(self, set_name: str) -> List[str]:
        """
        Get field list for predefined set (alias for get_fields).

        Args:
            set_name: Name of predefined field set (e.g., 'citations_minimal', 'citations_balanced')

        Returns:
            List of field names in the set
        """
        return self.get_fields(set_name)

    def _get_default_minimal_fields(self) -> List[str]:
        """Get default minimal fields."""
        return list(DEFAULT_MINIMAL_FIELDS)  # Use module-level constant

    def filter_response(self, response: Dict, set_name: str) -> Dict:
        """
        Filter API response to include only specified fields.
        Maintains response structure: {"response": {"start": X, "numFound": Y, "docs": [...]}}
        """
        try:
            fields = self.get_fields(set_name)
            if not fields:
                return response  # No filtering if no fields defined

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

        except Exception as e:
            logger.error(f"Response filtering failed for '{set_name}': {e}")
            return response  # Return original on error

    def validate_query_fields(self, query: str, field_set: str) -> Tuple[bool, str]:
        """Basic validation that query fields match available fields."""
        # This is a simple check - full Lucene validation in client
        allowed_fields = set(self.get_fields(field_set))
        # Extract field names from query (basic parsing)
        potential_fields = re.findall(r"(\w+):", query)
        invalid_fields = [f for f in potential_fields if f not in allowed_fields]

        if invalid_fields:
            return (
                False,
                f"Invalid fields in query for '{field_set}': {', '.join(invalid_fields[:3])}",
            )

        return True, "Field validation passed"

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

        except Exception as e:
            logger.error(f"Custom response filtering failed: {e}")
            return response  # Return original on error

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
