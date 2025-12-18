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

# Prompt for USPTO API key with validation loop and secure input
prompt_and_validate_uspto_key() {
    local key=""
    local max_attempts=3
    local attempt=0

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

# Export functions (for bash scripts that source this file)
export -f validate_uspto_api_key
export -f validate_mistral_api_key
export -f set_secure_file_permissions
export -f set_secure_directory_permissions
export -f mask_api_key
export -f read_api_key_secure
export -f prompt_and_validate_uspto_key
