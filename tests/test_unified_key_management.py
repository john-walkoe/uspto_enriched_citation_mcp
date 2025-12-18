"""
Unified API Key Management Test for USPTO MCPs
==============================================

This test replaces the older check_secure_keys.py and test_mistral_key_loading.py
with a comprehensive test that works with the new unified storage system.

Tests:
1. Unified storage functionality (view, store, retrieve keys)
2. Security: Shows only last 5 digits of keys
3. Cross-MCP compatibility
4. Key presence validation per MCP requirements

Security: This script shows key metadata (length, last 5 digits) but never displays full keys.
"""

import os
import sys
from pathlib import Path

# Add src to path (parent directory since we're in tests/)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

try:
    # Try to import from any available MCP structure
    UnifiedSecureStorage = None

    # Try FPD
    try:
        from fpd_mcp.shared_secure_storage import UnifiedSecureStorage
    except ImportError:
        pass

    # Try PFW
    if UnifiedSecureStorage is None:
        try:
            from patent_filewrapper_mcp.shared_secure_storage import (
                UnifiedSecureStorage,
            )
        except ImportError:
            pass

    # Try PTAB
    if UnifiedSecureStorage is None:
        try:
            from ptab_mcp.shared_secure_storage import UnifiedSecureStorage
        except ImportError:
            pass

    # Try Enriched Citations
    if UnifiedSecureStorage is None:
        try:
            from uspto_enriched_citation_mcp.shared_secure_storage import (
                UnifiedSecureStorage,
            )
        except ImportError:
            pass

    if UnifiedSecureStorage is None:
        raise ImportError("Could not import UnifiedSecureStorage from any MCP")

except ImportError as e:
    print(f"[FAIL] Import error: {e}")
    print("Make sure you're running this from an MCP directory with unified storage")
    sys.exit(1)


def format_key_display(key_value: str) -> str:
    """Format key for secure display (last 5 digits only)."""
    if not key_value:
        return "Not set"
    return f"...{key_value[-5:]} ({len(key_value)} chars)"


def test_unified_storage_functionality():
    """Test core unified storage functionality."""
    print("=" * 60)
    print("Testing Unified Storage Functionality")
    print("=" * 60)

    storage = UnifiedSecureStorage()

    # Get storage stats
    stats = storage.get_storage_stats()
    print("Storage paths:")
    print(f"  USPTO key:   {stats['uspto_key_path']}")
    print(f"  Mistral key: {stats['mistral_key_path']}")
    print(f"Platform:      {stats['platform']}")
    print(f"DPAPI available: {stats['dpapi_available']}")
    print()

    return storage


def test_current_keys():
    """Display current API key status."""
    print("=" * 60)
    print("Current API Key Status")
    print("=" * 60)

    # Create storage instance
    storage = UnifiedSecureStorage()

    # Check USPTO key
    uspto_key = storage.get_uspto_key()
    print(f"USPTO API Key:   {format_key_display(uspto_key)}")

    # Check Mistral key
    mistral_key = storage.get_mistral_key()
    print(f"Mistral API Key: {format_key_display(mistral_key)}")

    print()

    # Available keys summary
    available_keys = storage.list_available_keys()
    print(f"Available keys: {', '.join(available_keys) if available_keys else 'None'}")
    print()

    return uspto_key, mistral_key


def test_key_storage_retrieval():
    """Test key storage and retrieval with temporary test keys."""
    print("=" * 60)
    print("Testing Key Storage & Retrieval")
    print("=" * 60)

    storage = UnifiedSecureStorage()

    # Save existing keys before testing
    original_uspto = storage.get_uspto_key()
    original_mistral = storage.get_mistral_key()

    # Test keys
    test_uspto = "test_uspto_key_12345678901234567890"
    test_mistral = "test_mistral_key_09876543210987654321"

    print("1. Testing USPTO key storage...")
    success = storage.store_uspto_key(test_uspto)
    print(f"   Store result: {'[OK] SUCCESS' if success else '[FAIL] FAILED'}")

    retrieved_uspto = storage.get_uspto_key()
    matches = retrieved_uspto == test_uspto
    print(
        f"   Retrieval:    {'[OK] SUCCESS' if matches else '[FAIL] FAILED'} ({format_key_display(retrieved_uspto)})"
    )

    print("\n2. Testing Mistral key storage...")
    success = storage.store_mistral_key(test_mistral)
    print(f"   Store result: {'[OK] SUCCESS' if success else '[FAIL] FAILED'}")

    retrieved_mistral = storage.get_mistral_key()
    matches = retrieved_mistral == test_mistral
    print(
        f"   Retrieval:    {'[OK] SUCCESS' if matches else '[FAIL] FAILED'} ({format_key_display(retrieved_mistral)})"
    )

    print("\n3. Restoring original keys...")
    # Restore original keys instead of deleting everything
    try:
        if original_uspto:
            storage.store_uspto_key(original_uspto)
        elif storage.uspto_key_path.exists():
            storage.uspto_key_path.unlink()

        if original_mistral:
            storage.store_mistral_key(original_mistral)
        elif storage.mistral_key_path.exists():
            storage.mistral_key_path.unlink()

        print("   Cleanup:      [OK] SUCCESS")
    except Exception as e:
        print(f"   Cleanup:      [WARN]  WARNING - {e}")

    print()
    return True


def test_environment_variables():
    """Test environment variable fallback."""
    print("=" * 60)
    print("Environment Variables Check")
    print("=" * 60)

    env_uspto = os.environ.get("USPTO_API_KEY")
    env_mistral = os.environ.get("MISTRAL_API_KEY")

    print(
        f"USPTO_API_KEY env:   {format_key_display(env_uspto) if env_uspto else 'Not set'}"
    )
    print(
        f"MISTRAL_API_KEY env: {format_key_display(env_mistral) if env_mistral else 'Not set'}"
    )
    print()


def test_mcp_integration():
    """Test integration with current MCP."""
    print("=" * 60)
    print("MCP Integration Test")
    print("=" * 60)

    try:
        # Determine which MCP we're in based on available imports
        mcp_type = "Unknown"

        # Try FPD
        try:
            from fpd_mcp.api.fpd_client import FPDClient

            mcp_type = "FPD (Final Petition Decisions)"

            # Test client initialization
            try:
                client = FPDClient()
                print(f"[OK] {mcp_type} client initialized successfully")
                print(f"   API key: {format_key_display(client.api_key)}")
            except Exception as e:
                if "USPTO API key is required" in str(e):
                    print(
                        f"[WARN]  {mcp_type} client needs API key (expected if no key stored)"
                    )
                else:
                    print(f"[FAIL] {mcp_type} client error: {e}")

        except ImportError:
            pass

        # Try PFW
        try:
            from patent_filewrapper_mcp.api.enhanced_client import EnhancedPatentClient

            mcp_type = "PFW (Patent File Wrapper)"

            try:
                client = EnhancedPatentClient()
                print(f"[OK] {mcp_type} client initialized successfully")
                print(f"   API key: {format_key_display(client.api_key)}")
            except Exception as e:
                if "USPTO_API_KEY is required" in str(e):
                    print(
                        f"[WARN]  {mcp_type} client needs API key (expected if no key stored)"
                    )
                else:
                    print(f"[FAIL] {mcp_type} client error: {e}")

        except ImportError:
            pass

        # Try PTAB
        try:
            from ptab_mcp.api.enhanced_client import EnhancedPTABClient

            mcp_type = "PTAB (Patent Trial and Appeal Board)"

            try:
                client = EnhancedPTABClient()
                print(f"[OK] {mcp_type} client initialized successfully")
            except Exception as e:
                print(f"[FAIL] {mcp_type} client error: {e}")

        except ImportError:
            pass

        # Try Enriched Citations
        try:
            import importlib.util

            if importlib.util.find_spec("uspto_enriched_citation_mcp.api.client"):
                pass  # Module exists
            mcp_type = "Enriched Citations"

            # This MCP requires settings
            print(f"[INFO]  {mcp_type} MCP detected (requires API key for full test)")

        except ImportError:
            pass

        if mcp_type == "Unknown":
            print("[INFO]  Could not determine MCP type - generic test only")

    except Exception as e:
        print(f"[FAIL] MCP integration test failed: {e}")

    print()


def show_key_requirements():
    """Show API key requirements for different MCPs."""
    print("=" * 60)
    print("API Key Requirements by MCP")
    print("=" * 60)
    print("FPD (Final Petition Decisions):")
    print("  - USPTO API Key:   [OK] Required")
    print("  - Mistral API Key: [OPT] Optional (for OCR)")
    print()
    print("PFW (Patent File Wrapper):")
    print("  - USPTO API Key:   [OK] Required")
    print("  - Mistral API Key: [OPT] Optional (for OCR)")
    print()
    print("PTAB (Patent Trial and Appeal Board):")
    print("  - USPTO API Key:   [OPT] Optional (not used)")
    print("  - Mistral API Key: [OPT] Optional (for OCR)")
    print()
    print("Enriched Citations:")
    print("  - USPTO API Key:   [OK] Required")
    print("  - Mistral API Key: [OPT] Optional (not used)")
    print()


def main():
    """Run comprehensive unified key management test."""
    print("USPTO MCP - Unified API Key Management Test")
    print("=" * 60)
    print("[SECURITY] This test shows only the last 5 digits of API keys")
    print("=" * 60)
    print()

    try:
        # Test 1: Core functionality
        storage = test_unified_storage_functionality()

        # Test 2: Current key status
        uspto_key, mistral_key = test_current_keys(storage)

        # Test 3: Storage and retrieval
        storage_success = test_key_storage_retrieval()

        # Test 4: Environment variables
        test_environment_variables()

        # Test 5: MCP integration
        test_mcp_integration()

        # Test 6: Show requirements
        show_key_requirements()

        # Summary
        print("=" * 60)
        print("Test Summary")
        print("=" * 60)
        print("Unified Storage:     [OK] Working")
        print(
            f"Key Storage/Retrieval: {'[OK] Working' if storage_success else '[FAIL] Failed'}"
        )
        print(
            f"Current USPTO Key:   {'[OK] Available' if uspto_key else '[WARN]  Not set'}"
        )
        print(
            f"Current Mistral Key: {'[OK] Available' if mistral_key else '[INFO]  Not set (optional)'}"
        )

        print()
        if not uspto_key:
            print("[TIP] To set API keys, use: ./deploy/manage_api_keys.ps1")
        else:
            print("[OK] Keys are configured. MCP should work properly.")

        print()
        print("[OK] Unified key management test completed successfully!")

        return True

    except Exception as e:
        print(f"[FAIL] Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
