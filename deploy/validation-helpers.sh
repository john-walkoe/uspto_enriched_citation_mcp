#!/bin/bash
# Validation Helpers for USPTO MCP Deployment Scripts
# Provides secure API key format validation
# Compatible with all USPTO MCPs (FPD, PFW, PTAB, Enriched Citations)

# Validate USPTO API key format
# USPTO keys: 30 characters, all lowercase letters (a-z)
validate_uspto_api_key() {
    local key="$1"

    # Check if empty
    if [ -z "$key" ]; then
        echo "ERROR: USPTO API key cannot be empty"
        return 1
    fi

    # Check length (must be exactly 30 characters)
    if [ ${#key} -ne 30 ]; then
        echo "ERROR: USPTO API key must be exactly 30 characters"
        echo "       Current length: ${#key}"
        return 1
    fi

    # Check format: lowercase letters only (a-z)
    if ! echo "$key" | grep -qE '^[a-z]{30}$'; then
        echo "ERROR: USPTO API key must contain only lowercase letters (a-z)"
        echo "       Format: 30 lowercase letters"
        return 1
    fi

    echo "OK: USPTO API key format validated (30 lowercase letters)"
    return 0
}

# Validate Mistral API key format
# Mistral keys: 32 characters, letters (upper/lower case) and numbers
validate_mistral_api_key() {
    local key="$1"

    # Check if empty
    if [ -z "$key" ]; then
        echo "ERROR: Mistral API key cannot be empty"
        return 1
    fi

    # Check length (must be exactly 32 characters)
    if [ ${#key} -ne 32 ]; then
        echo "ERROR: Mistral API key must be exactly 32 characters"
        echo "       Current length: ${#key}"
        return 1
    fi

    # Check format: alphanumeric only (mixed case)
    if ! echo "$key" | grep -qE '^[a-zA-Z0-9]{32}$'; then
        echo "ERROR: Mistral API key must contain only letters and numbers"
        echo "       Format: 32 alphanumeric characters (mixed case)"
        return 1
    fi

    echo "OK: Mistral API key format validated (32 alphanumeric characters)"
    return 0
}

# Set secure file permissions (Unix: chmod 600)
# Restricts file to owner read/write only
set_secure_file_permissions() {
    local file_path="$1"

    if [ ! -f "$file_path" ]; then
        echo "ERROR: File not found: $file_path"
        return 1
    fi

    # Set restrictive permissions (owner read/write only)
    if chmod 600 "$file_path" 2>/dev/null; then
        # Verify permissions were set correctly
        local actual_perms
        if [ "$(uname)" = "Darwin" ]; then
            # macOS
            actual_perms=$(stat -f %A "$file_path")
        else
            # Linux
            actual_perms=$(stat -c %a "$file_path")
        fi

        if [ "$actual_perms" = "600" ]; then
            echo "OK: Secured file permissions: $file_path (600)"
            return 0
        else
            echo "WARN: Permissions set but verification failed (expected 600, got $actual_perms)"
            echo "      File: $file_path"
            return 1
        fi
    else
        echo "ERROR: Failed to set file permissions: $file_path"
        echo "       Please manually run: chmod 600 $file_path"
        return 1
    fi
}

# Set secure directory permissions (Unix: chmod 700)
# Restricts directory to owner read/write/execute only
set_secure_directory_permissions() {
    local dir_path="$1"

    if [ ! -d "$dir_path" ]; then
        echo "ERROR: Directory not found: $dir_path"
        return 1
    fi

    # Set restrictive permissions (owner read/write/execute only)
    if chmod 700 "$dir_path" 2>/dev/null; then
        # Verify permissions were set correctly
        local actual_perms
        if [ "$(uname)" = "Darwin" ]; then
            # macOS
            actual_perms=$(stat -f %A "$dir_path")
        else
            # Linux
            actual_perms=$(stat -c %a "$dir_path")
        fi

        if [ "$actual_perms" = "700" ]; then
            echo "OK: Secured directory permissions: $dir_path (700)"
            return 0
        else
            echo "WARN: Permissions set but verification failed (expected 700, got $actual_perms)"
            echo "      Directory: $dir_path"
            return 1
        fi
    else
        echo "ERROR: Failed to set directory permissions: $dir_path"
        echo "       Please manually run: chmod 700 $dir_path"
        return 1
    fi
}

# Mask API key for safe display (shows only last 5 characters)
mask_api_key() {
    local key="$1"

    if [ -z "$key" ]; then
        echo "Not set"
        return
    fi

    if [ ${#key} -le 5 ]; then
        echo "...$key"
        return
    fi

    local last5="${key: -5}"
    echo "...$last5"
}

# Securely read API key from user (hidden input)
read_api_key_secure() {
    local prompt="$1"
    local var_name="$2"
    local api_key=""

    # Read with hidden input (-s flag suppresses echo)
    read -r -s -p "$prompt: " api_key
    echo  # New line after hidden input

    # Return via eval (to set caller's variable)
    eval "$var_name='$api_key'"
}

# ============================================
# Existing Key Detection Functions
# ============================================

# Check if USPTO API key exists in secure storage
check_existing_uspto_key() {
    if [[ -f "$HOME/.uspto_api_key" ]]; then
        return 0  # Exists
    else
        return 1  # Does not exist
    fi
}

# Check if Mistral API key exists in secure storage
check_existing_mistral_key() {
    if [[ -f "$HOME/.mistral_api_key" ]]; then
        return 0  # Exists
    else
        return 1  # Does not exist
    fi
}

# Load existing USPTO key from secure storage
# SIMPLIFIED: Read directly from file (works across all USPTO MCPs)
load_existing_uspto_key() {
    local key_file="$HOME/.uspto_api_key"

    if [ ! -f "$key_file" ]; then
        return 1
    fi

    # Read the key file (plain text on Linux/macOS)
    local key=$(cat "$key_file" 2>/dev/null | tr -d '\n' | tr -d '\r')

    if [ -z "$key" ]; then
        return 1
    fi

    # Validate the key format (30 lowercase letters)
    if echo "$key" | grep -qE '^[a-z]{30}$'; then
        echo "$key"
        return 0
    else
        # Key file exists but format is invalid (may be corrupted)
        return 1
    fi
}

# Load existing Mistral key from secure storage
# SIMPLIFIED: Read directly from file (works across all USPTO MCPs)
load_existing_mistral_key() {
    local key_file="$HOME/.mistral_api_key"

    if [ ! -f "$key_file" ]; then
        return 1
    fi

    # Read the key file (plain text on Linux/macOS)
    local key=$(cat "$key_file" 2>/dev/null | tr -d '\n' | tr -d '\r')

    if [ -z "$key" ]; then
        return 1
    fi

    # Validate the key format (32 alphanumeric characters)
    if echo "$key" | grep -qE '^[a-zA-Z0-9]{32}$'; then
        echo "$key"
        return 0
    else
        # Key file exists but format is invalid (may be corrupted)
        return 1
    fi
}

# Prompt user if they want to use existing key
prompt_use_existing_key() {
    local key_type="$1"  # "USPTO" or "Mistral"
    local masked_key="$2"

    echo ""
    echo "SUCCESS: Detected existing $key_type API key from another USPTO MCP installation"
    echo "INFO: Key (masked): $masked_key"
    echo ""
    read -p "Would you like to use this existing key? (Y/n): " USE_EXISTING
    USE_EXISTING=${USE_EXISTING:-Y}

    if [[ "$USE_EXISTING" =~ ^[Yy]$ ]]; then
        return 0  # Use existing
    else
        return 1  # Don't use existing
    fi
}

# Prompt for USPTO API key with validation loop and secure input (with existing key detection)
prompt_and_validate_uspto_key() {
    local key=""
    local max_attempts=3
    local attempt=0

    # STEP 1: Check if key already exists in secure storage
    if check_existing_uspto_key; then
        echo "INFO: Checking existing USPTO API key from another USPTO MCP installation..."

        # Try to load the existing key
        local existing_key=$(load_existing_uspto_key)
        if [[ $? -eq 0 && -n "$existing_key" ]]; then
            # Mask the key for display
            local masked_key=$(mask_api_key "$existing_key")

            # Ask user if they want to use it
            if prompt_use_existing_key "USPTO" "$masked_key"; then
                echo "SUCCESS: Using existing USPTO API key from secure storage"
                echo "$existing_key"
                return 0
            else
                echo "INFO: You chose to enter a new USPTO API key"
                echo "WARN: This will OVERWRITE the existing key for ALL USPTO MCPs"
                read -p "Are you sure you want to continue? (y/N): " CONFIRM_OVERWRITE
                if [[ ! "$CONFIRM_OVERWRITE" =~ ^[Yy]$ ]]; then
                    echo "INFO: Keeping existing key"
                    echo "$existing_key"
                    return 0
                fi
            fi
        else
            echo "WARN: Existing key file found but could not load (may be corrupted)"
            echo "INFO: You will need to enter a new key"
        fi
    fi

    # STEP 2: Prompt for new key (either no existing key, or user wants to override)
    while [[ $attempt -lt $max_attempts ]]; do
        ((attempt++))

        read_api_key_secure "Enter your USPTO API key" key

        if [[ -z "$key" ]]; then
            echo "ERROR: USPTO API key cannot be empty"
            if [[ $attempt -lt $max_attempts ]]; then
                echo "INFO: Attempt $attempt of $max_attempts"
            fi
            continue
        fi

        # Validate the key
        VALIDATION_RESULT=$(validate_uspto_api_key "$key" 2>&1)
        if [ $? -eq 0 ]; then
            # Success - return key via echo
            echo "$key"
            return 0
        else
            echo "$VALIDATION_RESULT"
            if [[ $attempt -lt $max_attempts ]]; then
                echo "WARN: Attempt $attempt of $max_attempts - please try again"
                echo "INFO: USPTO API key format: 30 lowercase letters (a-z)"
            fi
        fi
    done

    echo "ERROR: Failed to provide valid USPTO API key after $max_attempts attempts"
    return 1
}

# Prompt for Mistral API key with validation loop (optional, with existing key detection)
prompt_and_validate_mistral_key() {
    local key=""
    local max_attempts=3
    local attempt=0

    # STEP 1: Check if key already exists in secure storage
    if check_existing_mistral_key; then
        echo "INFO: Checking existing Mistral API key from another USPTO MCP installation..."

        # Try to load the existing key
        local existing_key=$(load_existing_mistral_key)
        if [[ $? -eq 0 && -n "$existing_key" ]]; then
            # Mask the key for display
            local masked_key=$(mask_api_key "$existing_key")

            # Ask user if they want to use it
            if prompt_use_existing_key "Mistral" "$masked_key"; then
                echo "SUCCESS: Using existing Mistral API key from secure storage"
                echo "$existing_key"
                return 0
            else
                echo "INFO: You chose to enter a new Mistral API key"
                echo "WARN: This will OVERWRITE the existing key for ALL USPTO MCPs"
                read -p "Are you sure you want to continue? (y/N): " CONFIRM_OVERWRITE
                if [[ ! "$CONFIRM_OVERWRITE" =~ ^[Yy]$ ]]; then
                    echo "INFO: Keeping existing key"
                    echo "$existing_key"
                    return 0
                fi
            fi
        else
            echo "WARN: Existing key file found but could not load (may be corrupted)"
            echo "INFO: You will need to enter a new key"
        fi
    fi

    # STEP 2: Prompt for new key (either no existing key, or user wants to override)
    echo "INFO: Mistral API key is OPTIONAL (for OCR on scanned documents)"
    echo "INFO: Press Enter to skip, or enter your 32-character Mistral API key"
    echo

    while [[ $attempt -lt $max_attempts ]]; do
        ((attempt++))

        read_api_key_secure "Enter your Mistral API key (or press Enter to skip)" key

        # Empty is OK (optional)
        if [[ -z "$key" ]]; then
            echo "INFO: Skipping Mistral API key"
            echo ""  # Return empty string
            return 0
        fi

        # Validate the key
        VALIDATION_RESULT=$(validate_mistral_api_key "$key" 2>&1)
        if [ $? -eq 0 ]; then
            # Success - return key
            echo "$key"
            return 0
        else
            echo "$VALIDATION_RESULT"
            if [[ $attempt -lt $max_attempts ]]; then
                echo "WARN: Attempt $attempt of $max_attempts - please try again"
                echo "INFO: Mistral API key format: 32 alphanumeric characters (a-z, A-Z, 0-9)"
            fi
        fi
    done

    echo "ERROR: Failed to provide valid Mistral API key after $max_attempts attempts"
    return 1
}

# Export functions (for bash scripts that source this file)
export -f validate_uspto_api_key
export -f validate_mistral_api_key
export -f set_secure_file_permissions
export -f set_secure_directory_permissions
export -f mask_api_key
export -f read_api_key_secure
export -f check_existing_uspto_key
export -f check_existing_mistral_key
export -f load_existing_uspto_key
export -f load_existing_mistral_key
export -f prompt_use_existing_key
export -f prompt_and_validate_uspto_key
export -f prompt_and_validate_mistral_key
