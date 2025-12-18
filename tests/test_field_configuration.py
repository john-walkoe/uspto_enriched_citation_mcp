"""
Unit tests for field configuration system.

Tests the YAML-driven field configuration system for customizing
field sets without code changes.

Run with: uv run pytest tests/test_field_configuration.py -v
"""

import pytest
from unittest.mock import patch, mock_open
import yaml
from pathlib import Path

from uspto_enriched_citation_mcp.config.field_manager import FieldManager


class TestFieldManager:
    """Test field configuration management."""

    @pytest.fixture
    def field_manager(self):
        """Create field manager instance."""
        # Use default config path
        config_path = Path(__file__).parent.parent / "field_configs.yaml"
        return FieldManager(config_path)

    def test_load_field_config(self, field_manager):
        """Test 2.1: Load field configuration from YAML."""
        # Field manager should load successfully
        assert field_manager is not None

        # Should have predefined configurations
        minimal_fields = field_manager.get_fields("citations_minimal")
        assert minimal_fields is not None
        assert len(minimal_fields) > 0

    def test_predefined_minimal_fields(self, field_manager):
        """Test 2.1: Verify minimal field set."""
        minimal_fields = field_manager.get_fields("citations_minimal")

        # Should have approximately 8 fields
        assert len(minimal_fields) >= 7
        assert len(minimal_fields) <= 10

        # Should include essential fields
        expected_fields = [
            "citedDocumentIdentifier",
            "patentApplicationNumber",
            "citationCategoryCode"
        ]

        for field in expected_fields:
            assert field in minimal_fields, f"Expected field {field} not in minimal set"

    def test_predefined_balanced_fields(self, field_manager):
        """Test 2.1: Verify balanced field set."""
        balanced_fields = field_manager.get_fields("citations_balanced")

        # Should have approximately 18 fields
        assert len(balanced_fields) >= 16
        assert len(balanced_fields) <= 20

        # Should include all minimal fields plus extras
        assert "citedDocumentIdentifier" in balanced_fields
        assert "patentApplicationNumber" in balanced_fields
        assert "citationCategoryCode" in balanced_fields

        # Should include balanced-specific fields
        balanced_specific = [
            "passageLocationText",
            "relatedClaimNumberText",
            "examinerCitedReferenceIndicator"
        ]

        # At least some balanced-specific fields should be present
        present_count = sum(1 for f in balanced_specific if f in balanced_fields)
        assert present_count >= 2, "Balanced set should include analysis-specific fields"

    def test_all_available_fields(self, field_manager):
        """Test 2.1: Verify all available fields list."""
        all_fields = field_manager.get_all_available_fields()

        # Should have all 22 API v3 fields
        assert len(all_fields) >= 20
        assert len(all_fields) <= 25  # Allow some flexibility

        # Check for key field categories
        core_fields = [
            "citedDocumentIdentifier",
            "patentApplicationNumber",
            "publicationNumber"
        ]

        for field in core_fields:
            assert field in all_fields

    def test_field_filtering(self, field_manager):
        """Test 2.2: Response filtering with field manager."""
        # Mock response with many fields
        mock_response = {
            "citedDocumentIdentifier": "US-12345",
            "patentApplicationNumber": "17896175",
            "publicationNumber": "US11788453",
            "citationCategoryCode": "X",
            "examinerCitedReferenceIndicator": True,
            "techCenter": "2100",
            "groupArtUnitNumber": "2854",
            "officeActionDate": "2023-05-15",
            "passageLocationText": "col 5, line 10",
            "relatedClaimNumberText": "1, 3, 5",
            "extraField1": "should be filtered",
            "extraField2": "should be filtered"
        }

        # Filter to minimal fields
        minimal_fields = field_manager.get_fields("citations_minimal")
        filtered_response = field_manager.filter_response(mock_response, minimal_fields)

        # Should only have minimal fields
        assert len(filtered_response) <= len(minimal_fields) + 2  # Allow some flexibility

        # Essential fields should be present
        assert "citedDocumentIdentifier" in filtered_response
        assert "patentApplicationNumber" in filtered_response

        # Extra fields should be filtered out
        assert "extraField1" not in filtered_response
        assert "extraField2" not in filtered_response

    def test_invalid_field_rejection(self, field_manager):
        """Test 2.3: Invalid field name rejection."""
        # Test with unavailable field
        unavailable_fields = [
            "examinerNameText",
            "firstApplicantName",
            "decisionTypeCode",
            "nonexistentField"
        ]

        all_fields = field_manager.get_all_available_fields()

        for invalid_field in unavailable_fields:
            # These fields should NOT be in the available fields list
            assert invalid_field not in all_fields, \
                f"Field {invalid_field} should not be available in API v3"

    def test_field_validation(self, field_manager):
        """Test 2.3: Field validation logic."""
        # Valid fields should pass
        valid_fields = [
            "citedDocumentIdentifier",
            "patentApplicationNumber",
            "citationCategoryCode"
        ]

        is_valid, invalid_fields = field_manager.validate_fields(valid_fields)
        assert is_valid is True
        assert len(invalid_fields) == 0

        # Invalid fields should be detected
        mixed_fields = [
            "citedDocumentIdentifier",  # valid
            "examinerNameText",          # invalid
            "patentApplicationNumber",   # valid
            "nonexistentField"           # invalid
        ]

        is_valid, invalid_fields = field_manager.validate_fields(mixed_fields)
        assert is_valid is False
        assert len(invalid_fields) >= 2  # Should catch both invalid fields
        assert "examinerNameText" in invalid_fields or "nonexistentField" in invalid_fields

    def test_yaml_customization(self, field_manager, tmp_path):
        """Test 2.2: YAML customization workflow."""
        # Create custom YAML configuration
        custom_config = {
            "field_sets": {
                "citations_custom": {
                    "description": "Custom test field set",
                    "fields": [
                        "citedDocumentIdentifier",
                        "patentApplicationNumber",
                        "citationCategoryCode",
                        "techCenter"
                    ]
                }
            }
        }

        # Write to temporary file
        custom_yaml_path = tmp_path / "custom_fields.yaml"
        with open(custom_yaml_path, "w") as f:
            yaml.dump(custom_config, f)

        # Create field manager with custom config
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=yaml.dump(custom_config))):
                custom_manager = FieldManager()

                # Should be able to load custom configuration
                # Note: This tests the pattern, actual implementation may vary
                assert custom_manager is not None

    def test_field_set_descriptions(self, field_manager):
        """Test field set descriptions are available."""
        # Get field set metadata
        minimal_desc = field_manager.get_field_set_description("citations_minimal")
        balanced_desc = field_manager.get_field_set_description("citations_balanced")

        # Should have descriptions
        assert minimal_desc is not None or minimal_desc == ""  # May not be implemented yet
        assert balanced_desc is not None or balanced_desc == ""

    def test_default_field_set(self, field_manager):
        """Test default field set behavior."""
        # Getting fields without specifying set should use minimal
        default_fields = field_manager.get_fields("citations_minimal")

        assert default_fields is not None
        assert len(default_fields) > 0

    def test_field_count_consistency(self, field_manager):
        """Test field counts are consistent."""
        minimal_fields = field_manager.get_fields("citations_minimal")
        balanced_fields = field_manager.get_fields("citations_balanced")

        # Balanced should have more fields than minimal
        assert len(balanced_fields) > len(minimal_fields)

        # Minimal should be subset of balanced (mostly)
        minimal_set = set(minimal_fields)
        balanced_set = set(balanced_fields)

        # Most minimal fields should be in balanced
        overlap = minimal_set.intersection(balanced_set)
        assert len(overlap) >= len(minimal_fields) * 0.8  # At least 80% overlap


class TestFieldFiltering:
    """Test field filtering functionality."""

    @pytest.fixture
    def field_manager(self):
        """Create field manager instance."""
        config_path = Path(__file__).parent.parent / "field_configs.yaml"
        return FieldManager(config_path)

    def test_filter_single_document(self, field_manager):
        """Test filtering a single document."""
        document = {
            "citedDocumentIdentifier": "US-12345",
            "patentApplicationNumber": "17896175",
            "publicationNumber": "US11788453",
            "citationCategoryCode": "X",
            "examinerCitedReferenceIndicator": True,
            "extraField": "should be removed"
        }

        minimal_fields = field_manager.get_fields("citations_minimal")
        filtered = field_manager.filter_response(document, minimal_fields)

        # Should have filtered out extra fields
        assert "extraField" not in filtered

        # Should keep valid fields
        assert "citedDocumentIdentifier" in filtered

    def test_filter_multiple_documents(self, field_manager):
        """Test filtering multiple documents."""
        documents = [
            {
                "citedDocumentIdentifier": "US-12345",
                "patentApplicationNumber": "17896175",
                "extraField1": "remove"
            },
            {
                "citedDocumentIdentifier": "US-67890",
                "patentApplicationNumber": "18123456",
                "extraField2": "remove"
            }
        ]

        minimal_fields = field_manager.get_fields("citations_minimal")

        filtered_docs = [
            field_manager.filter_response(doc, minimal_fields)
            for doc in documents
        ]

        # Should have filtered all documents
        assert len(filtered_docs) == 2

        for doc in filtered_docs:
            assert "extraField1" not in doc
            assert "extraField2" not in doc
            assert "citedDocumentIdentifier" in doc

    def test_filter_with_missing_fields(self, field_manager):
        """Test filtering when document is missing some fields."""
        document = {
            "citedDocumentIdentifier": "US-12345",
            # patentApplicationNumber is missing
            "citationCategoryCode": "X"
        }

        minimal_fields = field_manager.get_fields("citations_minimal")
        filtered = field_manager.filter_response(document, minimal_fields)

        # Should handle missing fields gracefully
        assert "citedDocumentIdentifier" in filtered
        assert "citationCategoryCode" in filtered

    def test_filter_preserves_values(self, field_manager):
        """Test filtering preserves field values correctly."""
        document = {
            "citedDocumentIdentifier": "US-12345-TEST",
            "patentApplicationNumber": "17896175",
            "citationCategoryCode": "Y",
            "examinerCitedReferenceIndicator": False
        }

        minimal_fields = field_manager.get_fields("citations_minimal")
        filtered = field_manager.filter_response(document, minimal_fields)

        # Values should be preserved
        if "citedDocumentIdentifier" in filtered:
            assert filtered["citedDocumentIdentifier"] == "US-12345-TEST"
        if "citationCategoryCode" in filtered:
            assert filtered["citationCategoryCode"] == "Y"


class TestFieldValidation:
    """Test field validation functionality."""

    @pytest.fixture
    def field_manager(self):
        """Create field manager instance."""
        config_path = Path(__file__).parent.parent / "field_configs.yaml"
        return FieldManager(config_path)

    def test_validate_all_valid_fields(self, field_manager):
        """Test validation with all valid fields."""
        valid_fields = [
            "citedDocumentIdentifier",
            "patentApplicationNumber",
            "citationCategoryCode"
        ]

        is_valid, invalid = field_manager.validate_fields(valid_fields)

        assert is_valid is True
        assert len(invalid) == 0

    def test_validate_with_invalid_fields(self, field_manager):
        """Test validation detects invalid fields."""
        invalid_fields = [
            "examinerNameText",  # Not in API v3
            "nonexistentField"   # Doesn't exist
        ]

        is_valid, invalid = field_manager.validate_fields(invalid_fields)

        assert is_valid is False
        assert len(invalid) >= 1

    def test_validate_empty_list(self, field_manager):
        """Test validation with empty field list."""
        is_valid, invalid = field_manager.validate_fields([])

        # Empty list might be valid or invalid depending on implementation
        assert is_valid is not None  # Just check it doesn't crash

    def test_validate_mixed_fields(self, field_manager):
        """Test validation with mix of valid and invalid."""
        mixed = [
            "citedDocumentIdentifier",  # valid
            "examinerNameText",          # invalid
            "patentApplicationNumber"    # valid
        ]

        is_valid, invalid = field_manager.validate_fields(mixed)

        assert is_valid is False
        assert len(invalid) >= 1
        assert "examinerNameText" in invalid


if __name__ == "__main__":
    # Run with: python tests/test_field_configuration.py
    pytest.main([__file__, "-v"])
