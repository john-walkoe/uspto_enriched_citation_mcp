"""
Windows DPAPI Secure Storage for USPTO API Keys

This module provides secure storage and retrieval of API keys using Windows Data Protection API (DPAPI).
DPAPI encrypts data per-user and per-machine, so only the same user on the same machine can decrypt it.

No PowerShell execution policies or external dependencies required - uses only Python ctypes.
"""

import ctypes
import ctypes.wintypes
import os
import sys
from pathlib import Path
from typing import Optional, Union
from ..shared.enums import BackupPolicy


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


def encrypt_data(
    data: bytes, description: str = "USPTO Enriched Citation API Key"
) -> bytes:
    """
    Encrypt data using Windows DPAPI.

    Args:
        data: The data to encrypt (API key as bytes)
        description: Optional description for the encrypted data

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

    # NOTE: We do NOT use custom entropy parameter. DPAPI's built-in per-user,
    # per-machine encryption is sufficient. Using hardcoded entropy creates a
    # security vulnerability (CWE-330) as it can be extracted from source code.
    # Setting entropy to None relies on DPAPI's secure default behavior.

    # Call CryptProtectData
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    result = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(data_in),  # pDataIn
        description,  # szDataDescr
        None,  # pOptionalEntropy (secure default)
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


def decrypt_data(encrypted_data: bytes) -> bytes:
    """
    Decrypt data using Windows DPAPI.

    Args:
        encrypted_data: The encrypted data to decrypt

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

    # NOTE: Must match encryption - no custom entropy parameter.
    # DPAPI's built-in per-user, per-machine protection is used.

    # Prepare description pointer
    description_ptr = ctypes.wintypes.LPWSTR()

    # Call CryptUnprotectData
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    result = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(data_in),  # pDataIn
        ctypes.byref(description_ptr),  # ppszDataDescr
        None,  # pOptionalEntropy (secure default)
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
    decrypted_data = _get_data_from_blob(data_out)
    return decrypted_data


def _validate_uspto_api_key(api_key: str) -> bool:
    """
    Validate USPTO API key format.

    USPTO API keys are typically 32 lowercase alphanumeric characters.
    Example: your_api_key_here

    Args:
        api_key: The API key to validate

    Returns:
        True if valid format, False otherwise
    """
    if not api_key:
        return False

    # USPTO API keys are typically 32 characters, lowercase alphanumeric
    # Allow some flexibility in length (28-40 chars)
    if len(api_key) < 28 or len(api_key) > 40:
        return False

    # Should be alphanumeric (allowing for possible format changes)
    if not api_key.replace("-", "").replace("_", "").isalnum():
        return False

    return True


class SecureStorage:
    """Secure storage manager for USPTO API keys using Windows DPAPI."""

    def __init__(self, storage_file: Optional[str] = None):
        """
        Initialize secure storage.

        Args:
            storage_file: Path to storage file. Defaults to user profile location.
        """
        if storage_file is None:
            storage_file = os.path.join(
                os.path.expanduser("~"), ".uspto_enriched_citation_secure_key"
            )

        self.storage_file = Path(storage_file)

    def store_api_key(self, api_key: str) -> bool:
        """
        Store API key securely using Windows DPAPI.

        Args:
            api_key: The USPTO API key to store

        Returns:
            True if successful, False otherwise
        """
        try:
            if sys.platform != "win32":
                # Fall back to environment variable on non-Windows
                return False

            # Validate API key format
            if not _validate_uspto_api_key(api_key):
                raise ValueError("Invalid USPTO API key format")

            # Encrypt the API key
            encrypted_data = encrypt_data(api_key.encode("utf-8"))

            # Write to file
            self.storage_file.write_bytes(encrypted_data)

            # Set restrictive permissions (Windows - best effort)
            try:
                os.chmod(self.storage_file, 0o600)
            except Exception:
                pass  # Windows may not support chmod the same way

            return True

        except Exception:
            return False

    def get_api_key(self) -> Optional[str]:
        """
        Retrieve API key from secure storage.

        Returns:
            The decrypted API key, or None if not found/failed
        """
        try:
            if sys.platform != "win32":
                # Fall back to environment variable on non-Windows
                return os.environ.get("USPTO_ECITATION_API_KEY")

            if not self.storage_file.exists():
                # Fall back to environment variable if no secure storage
                return os.environ.get("USPTO_ECITATION_API_KEY")

            # Read encrypted data
            encrypted_data = self.storage_file.read_bytes()

            # Decrypt the API key
            decrypted_data = decrypt_data(encrypted_data)
            api_key = decrypted_data.decode("utf-8")

            # Validate decrypted key
            if _validate_uspto_api_key(api_key):
                return api_key
            else:
                # If decryption produces invalid key, fall back to env var
                return os.environ.get("USPTO_ECITATION_API_KEY")

        except Exception:
            # Fall back to environment variable on any error
            return os.environ.get("USPTO_ECITATION_API_KEY")

    def has_secure_key(self) -> bool:
        """
        Check if a secure key is stored.

        Returns:
            True if secure key exists and can be decrypted
        """
        try:
            api_key = self.get_api_key()
            return api_key is not None and _validate_uspto_api_key(api_key)
        except Exception:
            return False

    def remove_secure_key(self) -> bool:
        """
        Remove the secure key file.

        Returns:
            True if successful or file doesn't exist
        """
        try:
            if self.storage_file.exists():
                self.storage_file.unlink()
            return True
        except Exception:
            return False


def get_secure_api_key() -> Optional[str]:
    """
    Convenience function to get USPTO API key from secure storage.

    Returns:
        The API key, or None if not available
    """
    storage = SecureStorage()
    return storage.get_api_key()


def store_secure_api_key(api_key: str) -> bool:
    """
    Convenience function to store USPTO API key securely.

    Args:
        api_key: The USPTO API key to store

    Returns:
        True if successful
    """
    storage = SecureStorage()
    return storage.store_api_key(api_key)


def rotate_api_key(
    new_api_key: str, backup: Union[bool, BackupPolicy] = BackupPolicy.CREATE_BACKUP
) -> dict:
    """
    Rotate API key with automatic backup and rollback capability.

    This function safely rotates the API key by:
    1. Backing up the current key (if backup policy allows)
    2. Storing the new key
    3. Verifying the new key can be retrieved
    4. Providing rollback instructions if needed

    Args:
        new_api_key: The new USPTO API key to rotate to
        backup: Backup policy (BackupPolicy.CREATE_BACKUP or BackupPolicy.NO_BACKUP)
               For backward compatibility, also accepts bool (True=CREATE_BACKUP, False=NO_BACKUP)

    Returns:
        Dict with rotation status and details:
        {
            "success": bool,
            "message": str,
            "backup_file": str (if backup enabled),
            "rollback_available": bool
        }
    """
    # Convert bool to BackupPolicy for backward compatibility
    if isinstance(backup, bool):
        backup_policy = BackupPolicy.from_bool(backup)
    else:
        backup_policy = backup

    storage = SecureStorage()
    backup_path = None

    try:
        # Step 1: Backup current key if requested
        if backup_policy:
            current_key = storage.get_api_key()
            if current_key:
                backup_path = Path(str(storage.storage_file) + ".backup")
                backup_storage = SecureStorage(str(backup_path))
                if not backup_storage.store_api_key(current_key):
                    return {
                        "success": False,
                        "message": "Failed to backup current API key",
                        "backup_file": None,
                        "rollback_available": False,
                    }

        # Step 2: Store new API key
        if not storage.store_api_key(new_api_key):
            # If storage failed, restore from backup
            if backup_policy and backup_path and backup_path.exists():
                _restore_from_backup()
                return {
                    "success": False,
                    "message": "Failed to store new API key, restored from backup",
                    "backup_file": str(backup_path),
                    "rollback_available": True,
                }
            return {
                "success": False,
                "message": "Failed to store new API key",
                "backup_file": None,
                "rollback_available": False,
            }

        # Step 3: Verify new key can be retrieved
        retrieved_key = storage.get_api_key()
        if not retrieved_key or retrieved_key != new_api_key:
            # Verification failed, restore from backup
            if backup_policy and backup_path and backup_path.exists():
                _restore_from_backup()
                return {
                    "success": False,
                    "message": "Failed to verify new API key, restored from backup",
                    "backup_file": str(backup_path),
                    "rollback_available": True,
                }
            return {
                "success": False,
                "message": "Failed to verify new API key",
                "backup_file": None,
                "rollback_available": False,
            }

        # Success!
        return {
            "success": True,
            "message": "API key rotated successfully",
            "backup_file": str(backup_path) if backup_path else None,
            "rollback_available": backup and backup_path and backup_path.exists(),
        }

    except Exception as e:
        # On any error, attempt rollback
        if backup and backup_path and backup_path.exists():
            try:
                _restore_from_backup()
                return {
                    "success": False,
                    "message": f"Rotation failed: {str(e)}. Restored from backup.",
                    "backup_file": str(backup_path),
                    "rollback_available": True,
                }
            except Exception:
                pass

        return {
            "success": False,
            "message": f"Rotation failed: {str(e)}",
            "backup_file": str(backup_path) if backup_path else None,
            "rollback_available": False,
        }


def _restore_from_backup() -> bool:
    """
    Internal function to restore API key from backup.

    Returns:
        True if successful, False otherwise
    """
    try:
        storage = SecureStorage()
        backup_path = Path(str(storage.storage_file) + ".backup")

        if not backup_path.exists():
            return False

        backup_storage = SecureStorage(str(backup_path))
        backup_key = backup_storage.get_api_key()

        if not backup_key:
            return False

        return storage.store_api_key(backup_key)

    except Exception:
        return False


def rollback_api_key() -> dict:
    """
    Rollback to the backed-up API key.

    Returns:
        Dict with rollback status:
        {
            "success": bool,
            "message": str
        }
    """
    try:
        if _restore_from_backup():
            return {
                "success": True,
                "message": "Successfully rolled back to backup API key",
            }
        else:
            return {"success": False, "message": "No backup found or rollback failed"}
    except Exception as e:
        return {"success": False, "message": f"Rollback failed: {str(e)}"}


def cleanup_backup() -> bool:
    """
    Remove backup file after successful rotation.

    Returns:
        True if backup was removed or doesn't exist, False on error
    """
    try:
        storage = SecureStorage()
        backup_path = Path(str(storage.storage_file) + ".backup")

        if backup_path.exists():
            backup_path.unlink()

        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Simple test/demo
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Test encryption/decryption
            test_data = "your_api_key_here_32_characters"
            print("Testing DPAPI encryption/decryption...")

            try:
                encrypted = encrypt_data(test_data.encode("utf-8"))
                print(f"Encrypted: {len(encrypted)} bytes")

                decrypted = decrypt_data(encrypted)
                decrypted_str = decrypted.decode("utf-8")
                print(f"Decrypted: {decrypted_str}")

                if decrypted_str == test_data:
                    print("[SUCCESS] DPAPI test PASSED")
                else:
                    print("[FAILED] DPAPI test FAILED")

            except Exception as e:
                print(f"[FAILED] DPAPI test FAILED: {e}")

        elif sys.argv[1] == "store":
            if len(sys.argv) > 2:
                success = store_secure_api_key(sys.argv[2])
                print(
                    "[SUCCESS] API key stored securely"
                    if success
                    else "[FAILED] Failed to store API key"
                )
            else:
                print("Usage: python secure_storage.py store <api_key>")

        elif sys.argv[1] == "get":
            api_key = get_secure_api_key()
            if api_key:
                print(f"API key: {api_key[:10]}...")
            else:
                print("No API key found")

        elif sys.argv[1] == "rotate":
            if len(sys.argv) > 2:
                result = rotate_api_key(sys.argv[2])
                if result["success"]:
                    print(f"[SUCCESS] {result['message']}")
                    if result.get("backup_file"):
                        print(f"Backup saved to: {result['backup_file']}")
                        print("To rollback: python secure_storage.py rollback")
                        print("To cleanup backup: python secure_storage.py cleanup")
                else:
                    print(f"[FAILED] {result['message']}")
            else:
                print("Usage: python secure_storage.py rotate <new_api_key>")

        elif sys.argv[1] == "rollback":
            result = rollback_api_key()
            if result["success"]:
                print(f"[SUCCESS] {result['message']}")
            else:
                print(f"[FAILED] {result['message']}")

        elif sys.argv[1] == "cleanup":
            success = cleanup_backup()
            if success:
                print("[SUCCESS] Backup file removed")
            else:
                print("[FAILED] Failed to remove backup file")

    else:
        print("Usage:")
        print("  python secure_storage.py test          - Test DPAPI functionality")
        print("  python secure_storage.py store <key>   - Store API key")
        print("  python secure_storage.py get           - Retrieve API key")
        print(
            "  python secure_storage.py rotate <key>  - Rotate to new API key (with backup)"
        )
        print(
            "  python secure_storage.py rollback      - Rollback to backed-up API key"
        )
        print("  python secure_storage.py cleanup       - Remove backup file")
