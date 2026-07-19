<#
.SYNOPSIS
API Key and Input Validation Module for USPTO MCP Deployment (PowerShell)

.DESCRIPTION
Provides validation functions for USPTO and Mistral API keys, path validation,
and secure secret generation for Windows deployment scripts.

Security: Prevents deployment with invalid/placeholder keys
Part of: Security fixes for deploy scripts (audit findings)

.NOTES
Date: 2025-11-18
Author: USPTO MCP Security Team
Version: 1.0.0

.EXAMPLE
Import-Module .\Validation-Helpers.psm1
Test-UsptoApiKey -ApiKey $myKey
#>

# ============================================
# API Key Format Validation Functions
# ============================================

function Test-UsptoApiKey {
    <#
    .SYNOPSIS
    Validates USPTO API key format

    .DESCRIPTION
    USPTO API Key Format:
    - Length: Exactly 30 characters
    - Characters: Lowercase letters only (a-z)
    - Example: abcdefghijklmnopqrstuvwxyzabcd

    .PARAMETER ApiKey
    The API key to validate

    .PARAMETER Silent
    If specified, don't write output (return only)

    .OUTPUTS
    Boolean - $true if valid, $false if invalid

    .EXAMPLE
    Test-UsptoApiKey -ApiKey "abcdefghijklmnopqrstuvwxyzabcd"
    #>
    [CmdletBinding()]
    [OutputType([bool])]
    param(
        [Parameter(Mandatory=$true)]
        [string]$ApiKey,

        [Parameter(Mandatory=$false)]
        [switch]$Silent
    )

    # Check if empty
    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        if (-not $Silent) {
            Write-Host "[ERROR] USPTO API key is empty" -ForegroundColor Red
        }
        return $false
    }

    # Check exact length (30 characters)
    if ($ApiKey.Length -ne 30) {
        if (-not $Silent) {
            Write-Host "[ERROR] USPTO API key must be exactly 30 characters (got $($ApiKey.Length))" -ForegroundColor Red
            Write-Host "        Expected format: 30 lowercase letters (a-z)" -ForegroundColor Yellow
        }
        return $false
    }

    # Check character set (only lowercase letters)
    if ($ApiKey -notmatch '^[a-z]{30}$') {
        if (-not $Silent) {
            Write-Host "[ERROR] USPTO API key must contain only lowercase letters (a-z)" -ForegroundColor Red
            Write-Host "        Invalid characters detected in key" -ForegroundColor Yellow
        }
        return $false
    }

    # Check for placeholder patterns
    if (Test-PlaceholderPattern -Value $ApiKey -KeyType "USPTO" -Silent:$Silent) {
        return $false
    }

    # Check for obvious test patterns
    if ($ApiKey -match '^(test|demo|sample|example)') {
        if (-not $Silent) {
            Write-Host "[WARN] USPTO API key starts with 'test/demo/sample' - is this a real key?" -ForegroundColor Yellow
            $confirm = Read-Host "Continue anyway? (y/N)"
            if ($confirm -ne 'y' -and $confirm -ne 'Y') {
                Write-Host "[INFO] Validation cancelled by user" -ForegroundColor Yellow
                return $false
            }
        }
    }

    if (-not $Silent) {
        Write-Host "[OK] USPTO API key format validated (30 chars, lowercase)" -ForegroundColor Green
    }
    return $true
}

function Test-MistralApiKey {
    <#
    .SYNOPSIS
    Validates Mistral API key format

    .DESCRIPTION
    Mistral API Key Format:
    - Length: Exactly 32 characters
    - Characters: Letters (a-z, A-Z) and numbers (0-9)
    - Example: AbCdEfGh1234567890IjKlMnOp1234

    .PARAMETER ApiKey
    The API key to validate (can be empty - Mistral is optional)

    .PARAMETER Silent
    If specified, don't write output (return only)

    .OUTPUTS
    Boolean - $true if valid, $false if invalid

    .EXAMPLE
    Test-MistralApiKey -ApiKey "AbCdEfGh1234567890IjKlMnOp1234"
    #>
    [CmdletBinding()]
    [OutputType([bool])]
    param(
        [Parameter(Mandatory=$false)]
        [string]$ApiKey,

        [Parameter(Mandatory=$false)]
        [switch]$Silent
    )

    # Empty is allowed (Mistral is optional)
    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        if (-not $Silent) {
            Write-Host "[INFO] Mistral API key is optional - skipping validation" -ForegroundColor Cyan
        }
        return $true
    }

    # Check exact length (32 characters)
    if ($ApiKey.Length -ne 32) {
        if (-not $Silent) {
            Write-Host "[ERROR] Mistral API key must be exactly 32 characters (got $($ApiKey.Length))" -ForegroundColor Red
            Write-Host "        Expected format: 32 alphanumeric characters (a-z, A-Z, 0-9)" -ForegroundColor Yellow
        }
        return $false
    }

    # Check character set (letters and numbers only)
    if ($ApiKey -notmatch '^[a-zA-Z0-9]{32}$') {
        if (-not $Silent) {
            Write-Host "[ERROR] Mistral API key must contain only letters (a-z, A-Z) and numbers (0-9)" -ForegroundColor Red
            Write-Host "        Invalid characters detected in key" -ForegroundColor Yellow
        }
        return $false
    }

    # Check for placeholder patterns
    if (Test-PlaceholderPattern -Value $ApiKey -KeyType "Mistral" -Silent:$Silent) {
        return $false
    }

    # Check for obvious test patterns
    if ($ApiKey -match '^(test|demo|sample|example)') {
        if (-not $Silent) {
            Write-Host "[WARN] Mistral API key starts with 'test/demo/sample' - is this a real key?" -ForegroundColor Yellow
            $confirm = Read-Host "Continue anyway? (y/N)"
            if ($confirm -ne 'y' -and $confirm -ne 'Y') {
                Write-Host "[INFO] Validation cancelled by user" -ForegroundColor Yellow
                return $false
            }
        }
    }

    if (-not $Silent) {
        Write-Host "[OK] Mistral API key format validated (32 chars, alphanumeric)" -ForegroundColor Green
    }
    return $true
}

function Test-PlaceholderPattern {
    <#
    .SYNOPSIS
    Checks for common placeholder patterns in API keys

    .DESCRIPTION
    Detects common placeholder text like "your_api_key_here", "placeholder", etc.

    .PARAMETER Value
    The value to check

    .PARAMETER KeyType
    The type of key (for error messages)

    .PARAMETER Silent
    If specified, don't write output (return only)

    .OUTPUTS
    Boolean - $true if placeholder detected (invalid), $false if no placeholder
    #>
    [CmdletBinding()]
    [OutputType([bool])]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Value,

        [Parameter(Mandatory=$true)]
        [string]$KeyType,

        [Parameter(Mandatory=$false)]
        [switch]$Silent
    )

    # Common placeholder patterns
    $placeholderPatterns = @(
        'your.*key',
        'your.*api',
        'api.*key.*here',
        'placeholder',
        'insert.*key',
        'insert.*api',
        'replace.*me',
        'replace.*key',
        'changeme',
        'change.*me',
        'put.*key.*here',
        'add.*key.*here',
        'enter.*key',
        'paste.*key',
        'fill.*in'
    )

    # Check each pattern (case-insensitive)
    foreach ($pattern in $placeholderPatterns) {
        if ($Value -match $pattern) {
            if (-not $Silent) {
                Write-Host "[ERROR] Detected placeholder pattern in $KeyType API key: '$pattern'" -ForegroundColor Red
                Write-Host "        Please use your actual API key, not a placeholder" -ForegroundColor Yellow
            }
            return $true  # Placeholder found (error)
        }
    }

    return $false  # No placeholder found (success)
}

# ============================================
# Path Validation Functions
# ============================================

function Test-PathSecurity {
    <#
    .SYNOPSIS
    Validates directory path for security

    .DESCRIPTION
    Checks for:
    - Path traversal attempts (..)
    - Absolute vs relative paths
    - Sensitive system directories

    .PARAMETER Path
    The path to validate

    .PARAMETER PathName
    Description of the path (for error messages)

    .PARAMETER Silent
    If specified, don't write output (return only)

    .OUTPUTS
    Boolean - $true if valid, $false if invalid
    #>
    [CmdletBinding()]
    [OutputType([bool])]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path,

        [Parameter(Mandatory=$true)]
        [string]$PathName,

        [Parameter(Mandatory=$false)]
        [switch]$Silent
    )

    # Check if empty
    if ([string]::IsNullOrWhiteSpace($Path)) {
        if (-not $Silent) {
            Write-Host "[ERROR] $PathName cannot be empty" -ForegroundColor Red
        }
        return $false
    }

    # Check for path traversal attempts (..)
    if ($Path -match '\.\.') {
        if (-not $Silent) {
            Write-Host "[ERROR] $PathName contains path traversal (..): $Path" -ForegroundColor Red
            Write-Host "        This is a security risk - path rejected" -ForegroundColor Red
        }
        return $false
    }

    # Check for absolute path (Windows: C:\, D:\, etc.)
    if (-not ($Path -match '^[A-Za-z]:\\' -or $Path -match '^\\\\')) {
        if (-not $Silent) {
            Write-Host "[WARN] $PathName should be an absolute path" -ForegroundColor Yellow
            Write-Host "       Got: $Path" -ForegroundColor Yellow
            $confirm = Read-Host "Continue anyway? (y/N)"
            if ($confirm -ne 'y' -and $confirm -ne 'Y') {
                Write-Host "[INFO] Path validation rejected by user" -ForegroundColor Yellow
                return $false
            }
        }
    }

    # Warn about Windows system directories
    $systemDirs = @('C:\Windows', 'C:\Program Files', 'C:\Program Files (x86)', 'C:\ProgramData')
    foreach ($sysDir in $systemDirs) {
        if ($Path -like "$sysDir*") {
            if (-not $Silent) {
                Write-Host "[WARN] $PathName targets system directory: $Path" -ForegroundColor Yellow
                Write-Host "       This could require administrator privileges" -ForegroundColor Yellow
            }
            break
        }
    }

    if (-not $Silent) {
        Write-Host "[OK] $PathName validated: $Path" -ForegroundColor Green
    }
    return $true
}

# ============================================
# Secret Generation Functions
# ============================================

function New-SecureSecret {
    <#
    .SYNOPSIS
    Generates a cryptographically secure random secret

    .DESCRIPTION
    Uses .NET's RNGCryptoServiceProvider for secure random generation
    Returns base64-encoded secret

    .PARAMETER Length
    Length in bytes (default 32)

    .OUTPUTS
    String - Base64-encoded secure random secret

    .EXAMPLE
    $secret = New-SecureSecret -Length 32
    #>
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory=$false)]
        [int]$Length = 32
    )

    try {
        $bytes = New-Object byte[] $Length
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($bytes)
        $rng.Dispose()

        $secret = [System.Convert]::ToBase64String($bytes)
        return $secret
    }
    catch {
        Write-Host "[ERROR] Failed to generate secure secret: $_" -ForegroundColor Red
        return $null
    }
}

# ============================================
# User Input Functions
# ============================================

function Read-ApiKeySecure {
    <#
    .SYNOPSIS
    Prompts user for API key with hidden input

    .DESCRIPTION
    Reads API key input with masking (not visible on screen)

    .PARAMETER Prompt
    The prompt text to display

    .OUTPUTS
    String - The entered API key

    .EXAMPLE
    $key = Read-ApiKeySecure -Prompt "Enter your USPTO API key"
    #>
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Prompt
    )

    $secureString = Read-Host -Prompt $Prompt -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureString)
    $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    return $apiKey
}

function Read-UsptoApiKeyWithValidation {
    <#
    .SYNOPSIS
    Prompts for USPTO API key with validation loop

    .DESCRIPTION
    Repeatedly prompts user until a valid USPTO API key is entered

    .PARAMETER MaxAttempts
    Maximum number of attempts (default 3)

    .OUTPUTS
    String - Valid USPTO API key, or $null if failed

    .EXAMPLE
    $key = Read-UsptoApiKeyWithValidation
    #>
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory=$false)]
        [int]$MaxAttempts = 3
    )

    $attempt = 0

    while ($attempt -lt $MaxAttempts) {
        $attempt++

        $key = Read-ApiKeySecure -Prompt "Enter your USPTO API key"

        if ([string]::IsNullOrWhiteSpace($key)) {
            Write-Host "[ERROR] USPTO API key cannot be empty" -ForegroundColor Red
            if ($attempt -lt $MaxAttempts) {
                Write-Host "[INFO] Attempt $attempt of $MaxAttempts" -ForegroundColor Yellow
            }
            continue
        }

        if (Test-UsptoApiKey -ApiKey $key) {
            return $key
        }
        else {
            if ($attempt -lt $MaxAttempts) {
                Write-Host "[WARN] Attempt $attempt of $MaxAttempts - please try again" -ForegroundColor Yellow
                Write-Host "[INFO] USPTO API key format: 30 lowercase letters (a-z)" -ForegroundColor Cyan
            }
        }
    }

    Write-Host "[ERROR] Failed to provide valid USPTO API key after $MaxAttempts attempts" -ForegroundColor Red
    return $null
}

function Read-MistralApiKeyWithValidation {
    <#
    .SYNOPSIS
    Prompts for Mistral API key with validation loop (optional)

    .DESCRIPTION
    Repeatedly prompts user until a valid Mistral API key is entered or skipped

    .PARAMETER MaxAttempts
    Maximum number of attempts (default 3)

    .OUTPUTS
    String - Valid Mistral API key, empty string if skipped, or $null if failed

    .EXAMPLE
    $key = Read-MistralApiKeyWithValidation
    #>
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory=$false)]
        [int]$MaxAttempts = 3
    )

    Write-Host "[INFO] Mistral API key is OPTIONAL (for OCR on scanned documents)" -ForegroundColor Cyan
    Write-Host "[INFO] Press Enter to skip, or enter your 32-character Mistral API key" -ForegroundColor Cyan
    Write-Host ""

    $attempt = 0

    while ($attempt -lt $MaxAttempts) {
        $attempt++

        $key = Read-ApiKeySecure -Prompt "Enter your Mistral API key (or press Enter to skip)"

        # Empty is OK (optional)
        if ([string]::IsNullOrWhiteSpace($key)) {
            Write-Host "[INFO] Skipping Mistral API key (OCR disabled)" -ForegroundColor Yellow
            return ""
        }

        if (Test-MistralApiKey -ApiKey $key) {
            return $key
        }
        else {
            if ($attempt -lt $MaxAttempts) {
                Write-Host "[WARN] Attempt $attempt of $MaxAttempts - please try again" -ForegroundColor Yellow
                Write-Host "[INFO] Mistral API key format: 32 alphanumeric characters (a-z, A-Z, 0-9)" -ForegroundColor Cyan
            }
        }
    }

    Write-Host "[ERROR] Failed to provide valid Mistral API key after $MaxAttempts attempts" -ForegroundColor Red
    return $null
}

# ============================================
# Utility Functions
# ============================================

function Show-ApiKeyRequirements {
    <#
    .SYNOPSIS
    Displays API key format requirements

    .DESCRIPTION
    Shows formatted information about USPTO and Mistral API key requirements
    #>
    [CmdletBinding()]
    param()

    Write-Host ""
    Write-Host "API Key Format Requirements:" -ForegroundColor Cyan
    Write-Host "============================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "USPTO API Key:" -ForegroundColor White
    Write-Host "  - Required: YES" -ForegroundColor Green
    Write-Host "  - Length: Exactly 30 characters"
    Write-Host "  - Format: Lowercase letters only (a-z)"
    Write-Host "  - Example: abcdefghijklmnopqrstuvwxyzabcd"
    Write-Host "  - Get from: https://data.uspto.gov/myodp/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Mistral API Key:" -ForegroundColor White
    Write-Host "  - Required: NO (optional, for OCR)" -ForegroundColor Yellow
    Write-Host "  - Length: Exactly 32 characters"
    Write-Host "  - Format: Letters (a-z, A-Z) and numbers (0-9)"
    Write-Host "  - Example: AbCdEfGh1234567890IjKlMnOp1234"
    Write-Host "  - Get from: https://console.mistral.ai/" -ForegroundColor Yellow
    Write-Host ""
}

function Hide-ApiKey {
    <#
    .SYNOPSIS
    Masks API key for display (shows last 5 characters only)

    .PARAMETER ApiKey
    The API key to mask

    .PARAMETER VisibleChars
    Number of characters to show at end (default 5)

    .OUTPUTS
    String - Masked API key

    .EXAMPLE
    Hide-ApiKey -ApiKey "abcdefghijklmnopqrstuvwxyzabcd"
    # Returns: *************************abcd
    #>
    [CmdletBinding()]
    [OutputType([string])]
    param(
        [Parameter(Mandatory=$true)]
        [string]$ApiKey,

        [Parameter(Mandatory=$false)]
        [int]$VisibleChars = 5
    )

    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        return "[Not set]"
    }
    elseif ($ApiKey.Length -le $VisibleChars) {
        return "***"
    }
    else {
        $maskedLength = $ApiKey.Length - $VisibleChars
        $asterisks = '*' * $maskedLength
        $visible = $ApiKey.Substring($ApiKey.Length - $VisibleChars)
        return "$asterisks$visible"
    }
}

# ============================================
# Export Module Members
# ============================================

Export-ModuleMember -Function @(
    'Test-UsptoApiKey',
    'Test-MistralApiKey',
    'Test-PlaceholderPattern',
    'Test-PathSecurity',
    'New-SecureSecret',
    'Read-ApiKeySecure',
    'Read-UsptoApiKeyWithValidation',
    'Read-MistralApiKeyWithValidation',
    'Show-ApiKeyRequirements',
    'Hide-ApiKey'
)
