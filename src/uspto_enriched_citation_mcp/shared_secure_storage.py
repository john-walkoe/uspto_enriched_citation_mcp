"""
Unified USPTO MCP API Key Storage - Single Key Per File
========================================================

✅ CURRENT STANDARD - Use this module for all new code ✅

This module provides secure storage and retrieval of USPTO and Mistral API keys,
plus the shared INTERNAL_AUTH_SECRET, using Windows Data Protection API (DPAPI)
with single-key-per-file architecture.

Key Features:
- CWE-330 compliant: Uses secrets.token_bytes(32) for cryptographically secure entropy
- DPAPI encryption: Per-user, per-machine encryption on Windows
- Single responsibility: One file per key type
- Cross-platform: Graceful fallback to environment variables on non-Windows
- Simple API: get_uspto_key(), store_uspto_key(), get_mistral_key(), store_mistral_key()
- Shared secret: ensure_internal_auth_secret() for cross-MCP authentication

File Locations:
- Windows: C:\\Users\\{User}\\.uspto_api_key, C:\\Users\\{User}\\.mistral_api_key,
           C:\\Users\\{User}\\.uspto_internal_auth_secret
- Linux/macOS: ~/.uspto_api_key, ~/.mistral_api_key, ~/.uspto_internal_auth_secret

File Format:
- Bytes 0-31: Random entropy (32 bytes)
- Bytes 32+: DPAPI encrypted key data
"""

import ctypes
import ctypes.wintypes
import os
import secrets
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DATA_BLOB(ctypes.Structure):
    """Windows DATA_BLOB structure for DPAPI operations."""

    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _get_data_from_blob(blob: DATA_BLOB) -> bytes:
    """Extract bytes from a DATA_BLOB structure."""
    if not blob.cbData:
        return b""

    cbData = int(blob.cbData)
    pbData = blob.pbData
    buffer = ctypes.create_string_buffer(cbData)
    ctypes.memmove(buffer, pbData, cbData)
    ctypes.windll.kernel32.LocalFree(pbData)
    return buffer.raw


def _encrypt_with_dpapi(data: bytes, entropy: bytes) -> bytes:
    """
    Encrypt data using Windows DPAPI with custom entropy.

    Args:
        data: The data to encrypt
        entropy: Custom entropy for additional security

    Returns:
        Encrypted data as bytes

    Raises:
        OSError: If encryption fails
        RuntimeError: If not running on Windows
    """
    if sys.platform != "win32":
        raise RuntimeError("DPAPI is only available on Windows")

    # Prepare input data blob
    data_in = DATA_BLOB()
    data_in.pbData = ctypes.cast(
        ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_char)
    )
    data_in.cbData = len(data)

    # Prepare output data blob
    data_out = DATA_BLOB()

    # Prepare entropy blob
    entropy_blob = DATA_BLOB()
    entropy_blob.pbData = ctypes.cast(
        ctypes.create_string_buffer(entropy), ctypes.POINTER(ctypes.c_char)
    )
    entropy_blob.cbData = len(entropy)

    # Call CryptProtectData
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    result = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(data_in),  # pDataIn
        "USPTO MCP API Key",  # szDataDescr
        ctypes.byref(entropy_blob),  # pOptionalEntropy
        None,  # pvReserved
        None,  # pPromptStruct
        CRYPTPROTECT_UI_FORBIDDEN,  # dwFlags
        ctypes.byref(data_out),  # pDataOut
    )

    if not result:
        error_code = ctypes.windll.kernel32.GetLastError()
        raise OSError(f"CryptProtectData failed with error code: {error_code}")

    # Extract encrypted data
    encrypted_data = _get_data_from_blob(data_out)
    return encrypted_data


def _decrypt_with_dpapi(encrypted_data: bytes, entropy: bytes) -> bytes:
    """
    Decrypt data using Windows DPAPI with custom entropy.

    Args:
        encrypted_data: The encrypted data to decrypt
        entropy: Custom entropy used during encryption

    Returns:
        Decrypted data as bytes

    Raises:
        OSError: If decryption fails
        RuntimeError: If not running on Windows
    """
    if sys.platform != "win32":
        raise RuntimeError("DPAPI is only available on Windows")

    # Prepare input data blob
    data_in = DATA_BLOB()
    data_in.pbData = ctypes.cast(
        ctypes.create_string_buffer(encrypted_data), ctypes.POINTER(ctypes.c_char)
    )
    data_in.cbData = len(encrypted_data)

    # Prepare output data blob
    data_out = DATA_BLOB()

    # Prepare entropy blob
    entropy_blob = DATA_BLOB()
    entropy_blob.pbData = ctypes.cast(
        ctypes.create_string_buffer(entropy), ctypes.POINTER(ctypes.c_char)
    )
    entropy_blob.cbData = len(entropy)

    # Prepare description pointer
    description_ptr = ctypes.wintypes.LPWSTR()

    # Call CryptUnprotectData
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    result = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(data_in),  # pDataIn
        ctypes.byref(description_ptr),  # ppszDataDescr
        ctypes.byref(entropy_blob),  # pOptionalEntropy
        None,  # pvReserved
        None,  # pPromptStruct
        CRYPTPROTECT_UI_FORBIDDEN,  # dwFlags
        ctypes.byref(data_out),  # pDataOut
    )

    if not result:
        error_code = ctypes.windll.kernel32.GetLastError()
        raise OSError(f"CryptUnprotectData failed with error code: {error_code}")

    # Clean up description
    if description_ptr.value:
        ctypes.windll.kernel32.LocalFree(description_ptr)

    # Extract decrypted data
    return _get_data_from_blob(data_out)


class UnifiedSecureStorage:
    """
    Unified secure storage for USPTO MCP ecosystem.

    Provides simple, consistent API key storage across all USPTO MCPs:
    - Patent File Wrapper (PFW)
    - Final Petition Decisions (FPD)
    - PTAB Decisions
    - Enriched Citations

    Uses single-key-per-file architecture for maximum simplicity and security isolation.
    """

    def __init__(self):
        """Initialize unified secure storage."""
        self.home_dir = Path.home()
        self.uspto_key_path = self.home_dir / ".uspto_api_key"
        self.mistral_key_path = self.home_dir / ".mistral_api_key"
        self.internal_auth_secret_path = self.home_dir / ".uspto_internal_auth_secret"

        # Log storage paths for debugging
        logger.debug(f"USPTO key path: {self.uspto_key_path}")
        logger.debug(f"Mistral key path: {self.mistral_key_path}")
        logger.debug(f"Internal auth secret path: {self.internal_auth_secret_path}")

    def has_uspto_key(self) -> bool:
        """Check if USPTO API key exists in secure storage."""
        return self.uspto_key_path.exists()

    def has_mistral_key(self) -> bool:
        """Check if Mistral API key exists in secure storage."""
        return self.mistral_key_path.exists()

    def get_uspto_key(self) -> Optional[str]:
        """
        Retrieve USPTO API key from secure storage.

        Returns:
            USPTO API key string, or None if not found or decryption fails
        """
        return self._load_single_key(self.uspto_key_path, "USPTO_API_KEY")

    def store_uspto_key(self, key: str) -> bool:
        """
        Store USPTO API key in secure storage.

        Args:
            key: USPTO API key string

        Returns:
            True if successful, False otherwise
        """
        return self._store_single_key(key, self.uspto_key_path, "USPTO_API_KEY")

    def get_mistral_key(self) -> Optional[str]:
        """
        Retrieve Mistral API key from secure storage.

        Returns:
            Mistral API key string, or None if not found or decryption fails
        """
        return self._load_single_key(self.mistral_key_path, "MISTRAL_API_KEY")

    def store_mistral_key(self, key: str) -> bool:
        """
        Store Mistral API key in secure storage.

        Args:
            key: Mistral API key string

        Returns:
            True if successful, False otherwise
        """
        return self._store_single_key(key, self.mistral_key_path, "MISTRAL_API_KEY")

    def has_internal_auth_secret(self) -> bool:
        """Check if internal auth secret exists in secure storage."""
        return self.internal_auth_secret_path.exists()

    def get_internal_auth_secret(self) -> Optional[str]:
        """
        Retrieve internal auth secret from secure storage.

        This secret is SHARED across all 4 USPTO MCPs (FPD, PFW, PTAB, Citations)
        for inter-MCP authentication.

        Returns:
            Internal auth secret string, or None if not found or decryption fails
        """
        return self._load_single_key(self.internal_auth_secret_path, "INTERNAL_AUTH_SECRET")

    def store_internal_auth_secret(self, secret: str) -> bool:
        """
        Store internal auth secret in secure storage.

        This secret is SHARED across all 4 USPTO MCPs (FPD, PFW, PTAB, Citations)
        for inter-MCP authentication.

        Args:
            secret: Internal auth secret string (typically base64-encoded random bytes)

        Returns:
            True if successful, False otherwise
        """
        return self._store_single_key(secret, self.internal_auth_secret_path, "INTERNAL_AUTH_SECRET")

    def ensure_internal_auth_secret(self) -> str:
        """
        Ensure internal auth secret exists. Creates if missing.

        This implements the "first MCP wins" pattern - whoever installs first
        generates the secret, subsequent MCPs use the existing one.

        This ensures all 4 USPTO MCPs share the SAME secret for inter-MCP authentication.

        Returns:
            The internal auth secret (existing or newly generated)

        Raises:
            RuntimeError: If secret generation or storage fails
        """
        # Check if already exists
        existing = self.get_internal_auth_secret()
        if existing:
            logger.info("Using existing internal auth secret from unified storage")
            return existing

        # Generate new random secret (32 bytes, base64 encoded)
        import base64
        random_bytes = secrets.token_bytes(32)
        new_secret = base64.b64encode(random_bytes).decode('utf-8')

        logger.info("Generating new internal auth secret (first MCP installation)")

        # Store it
        if self.store_internal_auth_secret(new_secret):
            logger.info(f"Stored internal auth secret at: {self.internal_auth_secret_path}")
            return new_secret
        else:
            raise RuntimeError("Failed to store internal auth secret")

    def _store_single_key(self, key: str, path: Path, key_name: str) -> bool:
        """
        Store single key with CWE-330 compliant random entropy.

        Args:
            key: API key string to store
            path: File path for storage
            key_name: Key name for logging

        Returns:
            True if successful, False otherwise
        """
        try:
            if sys.platform == "win32":
                # Delete existing file if it exists (avoids permission issues on overwrite)
                if path.exists():
                    try:
                        path.unlink()
                        logger.debug(f"Deleted existing {key_name} file before writing new one")
                    except Exception as e:
                        logger.warning(f"Could not delete existing {key_name} file: {e}")
                        # Continue anyway - write_bytes might still work

                # Generate cryptographically secure random entropy (CWE-330 compliant)
                entropy = secrets.token_bytes(32)

                # Encrypt key data with DPAPI
                key_data = key.encode("utf-8")
                encrypted_data = _encrypt_with_dpapi(key_data, entropy)

                # Format: entropy (32 bytes) + encrypted_data
                file_data = entropy + encrypted_data

                # Write to file with restricted permissions
                path.write_bytes(file_data)

                # Set restrictive permissions (owner read/write only)
                if hasattr(os, "chmod"):
                    os.chmod(path, 0o600)

                logger.info(f"Stored {key_name} securely with 600 permissions")
                return True
            else:
                # Non-Windows: Store with basic file permissions (fallback)
                logger.warning(
                    "DPAPI not available - storing with file permissions only"
                )
                path.write_text(key, encoding="utf-8")

                if hasattr(os, "chmod"):
                    os.chmod(path, 0o600)

                logger.info(f"Stored {key_name} with file permissions (600)")
                return True

        except Exception as e:
            logger.error(f"Failed to store {key_name}: {e}")
            return False

    def _load_single_key(self, path: Path, key_name: str) -> Optional[str]:
        """
        Load single key with entropy extraction.

        Args:
            path: File path to load from
            key_name: Key name for logging

        Returns:
            Decrypted key string, or None if load fails
        """
        try:
            if not path.exists():
                logger.debug(f"{key_name} file not found in secure storage")
                return None

            if sys.platform == "win32":
                # Read encrypted file data
                file_data = path.read_bytes()

                if len(file_data) < 32:
                    logger.error(f"Invalid {key_name} file format: too short")
                    return None

                # Extract entropy and encrypted data
                entropy = file_data[:32]
                encrypted_data = file_data[32:]

                # Decrypt with DPAPI
                decrypted_data = _decrypt_with_dpapi(encrypted_data, entropy)
                key = decrypted_data.decode("utf-8")

                logger.debug(f"Loaded {key_name} from: {path}")
                return key
            else:
                # Non-Windows: Read plain text (fallback)
                key = path.read_text(encoding="utf-8").strip()
                logger.debug(f"Loaded {key_name} from: {path}")
                return key

        except Exception as e:
            logger.error(f"Failed to load {key_name}: {e}")
            return None

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics for debugging.

        Returns:
            Dictionary with storage status information
        """
        return {
            "uspto_key_exists": self.has_uspto_key(),
            "mistral_key_exists": self.has_mistral_key(),
            "internal_auth_secret_exists": self.has_internal_auth_secret(),
            "uspto_key_path": str(self.uspto_key_path),
            "mistral_key_path": str(self.mistral_key_path),
            "internal_auth_secret_path": str(self.internal_auth_secret_path),
            "platform": sys.platform,
            "dpapi_available": sys.platform == "win32",
        }

    def list_available_keys(self) -> list:
        """
        List available keys for debugging.

        Returns:
            List of available key names
        """
        keys = []
        if self.has_uspto_key():
            keys.append("USPTO_API_KEY")
        if self.has_mistral_key():
            keys.append("MISTRAL_API_KEY")
        if self.has_internal_auth_secret():
            keys.append("INTERNAL_AUTH_SECRET")
        return keys


# Convenience functions for backward compatibility and ease of use


def get_uspto_api_key() -> Optional[str]:
    """Convenience function to get USPTO API key."""
    return UnifiedSecureStorage().get_uspto_key()


def store_uspto_api_key(key: str) -> bool:
    """Convenience function to store USPTO API key."""
    return UnifiedSecureStorage().store_uspto_key(key)


def get_mistral_api_key() -> Optional[str]:
    """Convenience function to get Mistral API key."""
    return UnifiedSecureStorage().get_mistral_key()


def store_mistral_api_key(key: str) -> bool:
    """Convenience function to store Mistral API key."""
    return UnifiedSecureStorage().store_mistral_key(key)


def get_internal_auth_secret() -> Optional[str]:
    """Convenience function to get internal auth secret."""
    return UnifiedSecureStorage().get_internal_auth_secret()


def store_internal_auth_secret(secret: str) -> bool:
    """Convenience function to store internal auth secret."""
    return UnifiedSecureStorage().store_internal_auth_secret(secret)


def ensure_internal_auth_secret() -> str:
    """
    Convenience function to ensure internal auth secret exists.

    First MCP installation generates the secret, subsequent MCPs use existing one.
    This ensures all 4 USPTO MCPs share the SAME secret for authentication.

    Returns:
        The internal auth secret (existing or newly generated)

    Raises:
        RuntimeError: If secret generation or storage fails
    """
    return UnifiedSecureStorage().ensure_internal_auth_secret()


def has_secure_key(key_name: str) -> bool:
    """
    Check if a secure key exists (for backward compatibility).

    Args:
        key_name: "USPTO_API_KEY" or "MISTRAL_API_KEY"

    Returns:
        True if key exists, False otherwise
    """
    storage = UnifiedSecureStorage()
    if key_name == "USPTO_API_KEY":
        return storage.has_uspto_key()
    elif key_name == "MISTRAL_API_KEY":
        return storage.has_mistral_key()
    else:
        return False


def get_secure_api_key(key_name: str) -> Optional[str]:
    """
    Get a secure API key (for backward compatibility).

    Args:
        key_name: "USPTO_API_KEY" or "MISTRAL_API_KEY"

    Returns:
        API key string or None
    """
    storage = UnifiedSecureStorage()
    if key_name == "USPTO_API_KEY":
        return storage.get_uspto_key()
    elif key_name == "MISTRAL_API_KEY":
        return storage.get_mistral_key()
    else:
        return None


def store_secure_api_key(key: str, key_name: str) -> bool:
    """
    Store a secure API key (for backward compatibility).

    Args:
        key: API key string
        key_name: "USPTO_API_KEY" or "MISTRAL_API_KEY"

    Returns:
        True if successful, False otherwise
    """
    storage = UnifiedSecureStorage()
    if key_name == "USPTO_API_KEY":
        return storage.store_uspto_key(key)
    elif key_name == "MISTRAL_API_KEY":
        return storage.store_mistral_key(key)
    else:
        return False


# Test function
if __name__ == "__main__":
    print("Testing Unified Secure Storage...")

    storage = UnifiedSecureStorage()
    print("Storage stats:", storage.get_storage_stats())
    print("Available keys:", storage.list_available_keys())

    # Test encryption/decryption if on Windows
    if sys.platform == "win32":
        test_key = "test_api_key_12345"
        print(f"Testing with key: {test_key}")

        success = storage.store_uspto_key(test_key)
        print(f"Store success: {success}")

        retrieved_key = storage.get_uspto_key()
        print(f"Retrieved key: {retrieved_key}")
        print(f"Keys match: {test_key == retrieved_key}")

        # Clean up test
        if storage.uspto_key_path.exists():
            storage.uspto_key_path.unlink()
            print("Test file cleaned up")
    else:
        print("DPAPI testing skipped (not Windows)")
