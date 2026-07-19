# Universal USPTO MCP API Key Management Script
# =============================================
#
# This script works identically across all 4 USPTO MCPs:
# - FPD (Final Petition Decisions)
# - PFW (Patent File Wrapper)
# - PTAB (Patent Trial and Appeal Board)
# - Enriched Citations
#
# Features:
# - View current API keys (shows last 5 digits only for security)
# - Update USPTO and Mistral API keys with validation
# - Remove API keys
# - Test API key access
# - Run migration utilities
# - Uses unified secure storage system

param(
    [switch]$Help
)

# Import validation helpers
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module "$ScriptDir\Validation-Helpers.psm1" -Force

# Check if help is requested
if ($Help) {
    Write-Host "USPTO MCP API Key Management Script" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\manage_api_keys.ps1"
    Write-Host ""
    Write-Host "Features:"
    Write-Host "  - View current API keys (secure - last 5 digits only)"
    Write-Host "  - Update USPTO and Mistral API keys"
    Write-Host "  - Remove API keys"
    Write-Host "  - Test API key functionality"
    Write-Host "  - Run migration from legacy storage"
    Write-Host ""
    Write-Host "Security: API keys are encrypted using Windows DPAPI"
    Write-Host "Keys are stored in unified format across all USPTO MCPs"
    exit 0
}

# Note: Uses Validation-Helpers.psm1 for all key validation and input handling:
#   - Read-UsptoApiKeyWithValidation (3-attempt retry logic)
#   - Read-MistralApiKeyWithValidation (3-attempt retry logic, optional)
#   - Hide-ApiKey (secure display masking)
#   - Test-UsptoApiKey, Test-MistralApiKey (format validation)

# Function to test if uv and Python are available
function Test-Requirements {
    try {
        $uvVersion = uv --version 2>$null
        if (-not $uvVersion) {
            Write-Host "[ERROR] uv package manager is required but not found" -ForegroundColor Red
            Write-Host "        Please install uv: https://github.com/astral-sh/uv" -ForegroundColor Yellow
            return $false
        }
        return $true
    } catch {
        Write-Host "[ERROR] uv package manager is required but not found" -ForegroundColor Red
        Write-Host "        Please install uv: https://github.com/astral-sh/uv" -ForegroundColor Yellow
        return $false
    }
}

# Function to get current API key status
function Get-ApiKeyStatus {
    try {
        # Use direct Python path to avoid diagnostic messages
        $pythonExe = ".venv/Scripts/python.exe"
        if (-not (Test-Path $pythonExe)) {
            return $null
        }

        $pythonCode = @'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))

try:
    # Try to import from current MCP structure
    try:
        from fpd_mcp.shared_secure_storage import UnifiedSecureStorage
    except ImportError:
        try:
            from patent_filewrapper_mcp.shared_secure_storage import UnifiedSecureStorage
        except ImportError:
            try:
                from ptab_mcp.shared_secure_storage import UnifiedSecureStorage
            except ImportError:
                from uspto_enriched_citation_mcp.shared_secure_storage import UnifiedSecureStorage

    storage = UnifiedSecureStorage()
    uspto_key = storage.get_uspto_key()
    mistral_key = storage.get_mistral_key()

    # Return in parseable format
    print('USPTO:' + (uspto_key if uspto_key else ''))
    print('MISTRAL:' + (mistral_key if mistral_key else ''))

except Exception as e:
    print('ERROR:' + str(e))
'@

        $result = & $pythonExe -c $pythonCode 2>$null | Out-String

        if ($LASTEXITCODE -eq 0) {
            # Parse the result
            $lines = $result -split "`n"
            $usptoKey = ""
            $mistralKey = ""
            $error = ""

            foreach ($line in $lines) {
                if ($line.StartsWith("USPTO:")) {
                    $usptoKey = $line.Substring(6)
                } elseif ($line.StartsWith("MISTRAL:")) {
                    $mistralKey = $line.Substring(8)
                } elseif ($line.StartsWith("ERROR:")) {
                    $error = $line.Substring(6)
                }
            }

            if ($error) {
                Write-Host "[ERROR] Failed to check API keys: $error" -ForegroundColor Red
                return $null
            }

            return @{
                "USPTO" = $usptoKey
                "Mistral" = $mistralKey
            }
        } else {
            Write-Host "[ERROR] Failed to check API key status" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            return $null
        }
    } catch {
        Write-Host "[ERROR] Failed to check API key status: $_" -ForegroundColor Red
        return $null
    }
}

# Function to store API key
function Set-ApiKey {
    param(
        [string]$KeyType,
        [string]$ApiKey
    )

    try {
        # Use direct Python path to avoid file locking issues with uv
        $pythonExe = ".venv/Scripts/python.exe"
        if (-not (Test-Path $pythonExe)) {
            Write-Host "[ERROR] Python virtual environment not found at: $pythonExe" -ForegroundColor Red
            Write-Host "        Please run windows_setup.ps1 first to create the virtual environment" -ForegroundColor Yellow
            return $false
        }

        $pythonFunction = if ($KeyType -eq "USPTO") { "store_uspto_key" } else { "store_mistral_key" }

        $pythonCode = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))

try:
    # Try to import from current MCP structure
    try:
        from fpd_mcp.shared_secure_storage import UnifiedSecureStorage
    except ImportError:
        try:
            from patent_filewrapper_mcp.shared_secure_storage import UnifiedSecureStorage
        except ImportError:
            try:
                from ptab_mcp.shared_secure_storage import UnifiedSecureStorage
            except ImportError:
                from uspto_enriched_citation_mcp.shared_secure_storage import UnifiedSecureStorage

    storage = UnifiedSecureStorage()
    success = storage.$pythonFunction('$ApiKey')
    print('SUCCESS' if success else 'FAILED')

except Exception as e:
    print('ERROR: ' + str(e))
"@

        $result = & $pythonExe -c $pythonCode 2>$null | Out-String

        # Parse result - look for SUCCESS anywhere in output (ignore diagnostic messages)
        if ($result -match "SUCCESS") {
            Write-Host "[OK] $KeyType API key stored successfully" -ForegroundColor Green
            return $true
        } elseif ($result -match "ERROR:") {
            # Extract error message
            $errorMatch = [regex]::Match($result, "ERROR:\s*(.+)")
            if ($errorMatch.Success) {
                Write-Host "[ERROR] Failed to store $KeyType API key: $($errorMatch.Groups[1].Value)" -ForegroundColor Red
            } else {
                Write-Host "[ERROR] Failed to store $KeyType API key: $result" -ForegroundColor Red
            }
            return $false
        } else {
            Write-Host "[ERROR] Failed to store $KeyType API key: Unexpected output" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "[ERROR] Failed to store $KeyType API key: $_" -ForegroundColor Red
        return $false
    }
}

# Function to remove API keys
function Remove-ApiKeys {
    param([switch]$All, [switch]$USPTO, [switch]$Mistral)

    try {
        # Use direct Python path to avoid diagnostic messages
        $pythonExe = ".venv/Scripts/python.exe"
        if (-not (Test-Path $pythonExe)) {
            Write-Host "[ERROR] Python virtual environment not found" -ForegroundColor Red
            return $false
        }

        $pythonCode = @"
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))

try:
    # Try to import from current MCP structure
    try:
        from fpd_mcp.shared_secure_storage import UnifiedSecureStorage
    except ImportError:
        try:
            from patent_filewrapper_mcp.shared_secure_storage import UnifiedSecureStorage
        except ImportError:
            try:
                from ptab_mcp.shared_secure_storage import UnifiedSecureStorage
            except ImportError:
                from uspto_enriched_citation_mcp.shared_secure_storage import UnifiedSecureStorage

    storage = UnifiedSecureStorage()
    removed = []

    if '$All' == 'True' or '$USPTO' == 'True':
        if storage.uspto_key_path.exists():
            storage.uspto_key_path.unlink()
            removed.append('USPTO')

    if '$All' == 'True' or '$Mistral' == 'True':
        if storage.mistral_key_path.exists():
            storage.mistral_key_path.unlink()
            removed.append('MISTRAL')

    print(','.join(removed) if removed else 'NONE')

except Exception as e:
    print('ERROR: ' + str(e))
"@

        $result = & $pythonExe -c $pythonCode 2>$null | Out-String

        if ($result.StartsWith("ERROR:")) {
            Write-Host "[ERROR] Failed to remove API keys: $($result.Substring(6))" -ForegroundColor Red
            return $false
        } else {
            $removed = $result.Trim()
            if ($removed -eq "NONE") {
                Write-Host "[INFO] No API keys found to remove" -ForegroundColor Yellow
            } else {
                Write-Host "[OK] Removed API keys: $removed" -ForegroundColor Green
            }
            return $true
        }
    } catch {
        Write-Host "[ERROR] Failed to remove API keys: $_" -ForegroundColor Red
        return $false
    }
}

# Function to test API key functionality
function Test-ApiKeys {
    Write-Host ""
    Write-Host "Testing API Key Functionality" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan
    Write-Host ""

    try {
        # Use direct Python path to avoid diagnostic messages
        $pythonExe = ".venv/Scripts/python.exe"
        if (-not (Test-Path $pythonExe)) {
            Write-Host "[ERROR] Python virtual environment not found" -ForegroundColor Red
            return
        }

        $pythonCode = @'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))

try:
    # Try to import from current MCP structure
    try:
        from fpd_mcp.shared_secure_storage import UnifiedSecureStorage
    except ImportError:
        try:
            from patent_filewrapper_mcp.shared_secure_storage import UnifiedSecureStorage
        except ImportError:
            try:
                from ptab_mcp.shared_secure_storage import UnifiedSecureStorage
            except ImportError:
                from uspto_enriched_citation_mcp.shared_secure_storage import UnifiedSecureStorage

    storage = UnifiedSecureStorage()

    # Test key retrieval
    uspto_key = storage.get_uspto_key()
    mistral_key = storage.get_mistral_key()

    # Format output
    print('STORAGE_PATHS:')
    print('  USPTO:   ' + str(storage.uspto_key_path))
    print('  Mistral: ' + str(storage.mistral_key_path))
    print('')

    print('KEY_STATUS:')
    if uspto_key:
        print('  USPTO:   Available (...' + uspto_key[-5:] + ', ' + str(len(uspto_key)) + ' chars)')
    else:
        print('  USPTO:   Not set')

    if mistral_key:
        print('  Mistral: Available (...' + mistral_key[-5:] + ', ' + str(len(mistral_key)) + ' chars)')
    else:
        print('  Mistral: Not set')
    print('')

    # Validate key formats
    print('VALIDATION:')
    issues = []

    if uspto_key:
        if len(uspto_key) != 30:
            issues.append('  USPTO key length is ' + str(len(uspto_key)) + ' chars (expected 30)')
        elif not uspto_key.islower() or not uspto_key.isalpha():
            issues.append('  USPTO key format invalid (expected lowercase letters only)')
        else:
            print('  USPTO:   Format OK (30 chars, lowercase)')
    else:
        issues.append('  USPTO key not found (required for most MCPs)')

    if mistral_key:
        if len(mistral_key) != 32:
            issues.append('  Mistral key length is ' + str(len(mistral_key)) + ' chars (expected 32)')
        elif not mistral_key.isalnum():
            issues.append('  Mistral key format invalid (expected alphanumeric)')
        else:
            print('  Mistral: Format OK (32 chars, alphanumeric)')
    else:
        print('  Mistral: Not set (optional, for OCR functionality)')

    if issues:
        print('')
        print('ISSUES:')
        for issue in issues:
            print(issue)

    print('')
    if not issues:
        print('RESULT:SUCCESS')
    else:
        print('RESULT:WARNINGS')

except Exception as e:
    print('ERROR:' + str(e))
'@

        $result = & $pythonExe -c $pythonCode 2>$null | Out-String

        # Parse and format the output
        $lines = $result -split "`n"
        foreach ($line in $lines) {
            if ($line -match "^ERROR:") {
                Write-Host $line.Replace("ERROR:", "[ERROR] ") -ForegroundColor Red
            }
            elseif ($line -match "^STORAGE_PATHS:") {
                Write-Host "Storage Locations:" -ForegroundColor Cyan
            }
            elseif ($line -match "^KEY_STATUS:") {
                Write-Host "`nCurrent Status:" -ForegroundColor Cyan
            }
            elseif ($line -match "^VALIDATION:") {
                Write-Host "`nValidation:" -ForegroundColor Cyan
            }
            elseif ($line -match "^ISSUES:") {
                Write-Host "`nIssues Found:" -ForegroundColor Yellow
            }
            elseif ($line -match "^RESULT:SUCCESS") {
                Write-Host "`n[OK] All API keys are properly configured and validated" -ForegroundColor Green
            }
            elseif ($line -match "^RESULT:WARNINGS") {
                Write-Host "`n[WARN] Some issues detected - see above" -ForegroundColor Yellow
            }
            elseif ($line.Trim() -ne "") {
                Write-Host $line
            }
        }

    } catch {
        Write-Host "[ERROR] Failed to run API key tests: $_" -ForegroundColor Red
    }
}

# Function to determine which MCP this is
function Get-McpType {
    if (Test-Path "src\fpd_mcp") {
        return "FPD (Final Petition Decisions)"
    } elseif (Test-Path "src\patent_filewrapper_mcp") {
        return "PFW (Patent File Wrapper)"
    } elseif (Test-Path "src\ptab_mcp") {
        return "PTAB (Patent Trial and Appeal Board)"
    } elseif (Test-Path "src\uspto_enriched_citation_mcp") {
        return "Enriched Citations"
    } else {
        return "Unknown MCP"
    }
}

# Function to view INTERNAL_AUTH_SECRET
function Show-InternalAuthSecret {
    Write-Host ""
    Write-Host "View INTERNAL_AUTH_SECRET" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[INFO] This secret is SHARED across all 4 USPTO MCPs for inter-MCP authentication" -ForegroundColor Yellow
    Write-Host "[INFO] All MCPs (FPD, PFW, PTAB, Citations) must use the SAME value" -ForegroundColor Yellow
    Write-Host ""

    try {
        # Use direct Python path to avoid diagnostic messages
        $pythonExe = ".venv/Scripts/python.exe"
        if (-not (Test-Path $pythonExe)) {
            Write-Host "[ERROR] Python virtual environment not found" -ForegroundColor Red
            return
        }

        $pythonCode = @'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))

try:
    # Try to import from current MCP structure
    try:
        from fpd_mcp.shared_secure_storage import UnifiedSecureStorage
    except ImportError:
        try:
            from patent_filewrapper_mcp.shared_secure_storage import UnifiedSecureStorage
        except ImportError:
            try:
                from ptab_mcp.shared_secure_storage import UnifiedSecureStorage
            except ImportError:
                from uspto_enriched_citation_mcp.shared_secure_storage import UnifiedSecureStorage

    storage = UnifiedSecureStorage()
    secret = storage.get_internal_auth_secret()

    if secret:
        print('SECRET:' + secret)
        print('PATH:' + str(storage.internal_auth_secret_path))
    else:
        print('ERROR:Not found')

except Exception as e:
    print('ERROR:' + str(e))
'@

        $result = & $pythonExe -c $pythonCode 2>$null | Out-String

        # Parse the result
        $lines = $result -split "`n"
        $secret = $null
        $path = $null
        $error = $null

        foreach ($line in $lines) {
            if ($line -match "^SECRET:(.+)") {
                $secret = $matches[1]
            }
            elseif ($line -match "^PATH:(.+)") {
                $path = $matches[1]
            }
            elseif ($line -match "^ERROR:(.+)") {
                $error = $matches[1]
            }
        }

        if ($error) {
            Write-Host "[ERROR] $error" -ForegroundColor Red
            Write-Host ""
            Write-Host "The INTERNAL_AUTH_SECRET has not been generated yet." -ForegroundColor Yellow
            Write-Host "Run the setup script to generate it: .\deploy\windows_setup.ps1" -ForegroundColor Yellow
        }
        elseif ($secret) {
            Write-Host "Storage Location:" -ForegroundColor Cyan
            Write-Host "  $path" -ForegroundColor White
            Write-Host ""
            Write-Host "INTERNAL_AUTH_SECRET Value:" -ForegroundColor Cyan
            Write-Host "  $secret" -ForegroundColor Green
            Write-Host ""

            # Get MCP type for config example
            $mcpType = Get-McpType

            Write-Host "DPAPI Mode - Claude Desktop Config Example ($mcpType):" -ForegroundColor Cyan
            Write-Host ("=" * 60) -ForegroundColor Cyan
            Write-Host ""

            # Show MCP-specific config
            switch -Wildcard ($mcpType) {
                "*FPD*" {
                    Write-Host '{' -ForegroundColor Gray
                    Write-Host '  "mcpServers": {' -ForegroundColor Gray
                    Write-Host '    "uspto_fpd": {' -ForegroundColor Gray
                    Write-Host '      "command": "C:/Users/YOUR_USERNAME/uspto_fpd_mcp/.venv/Scripts/python.exe",' -ForegroundColor Gray
                    Write-Host '      "args": ["-m", "fpd_mcp.main"],' -ForegroundColor Gray
                    Write-Host '      "cwd": "C:/Users/YOUR_USERNAME/uspto_fpd_mcp",' -ForegroundColor Gray
                    Write-Host '      "env": {' -ForegroundColor Gray
                    Write-Host '        "INTERNAL_AUTH_SECRET": "' -NoNewline -ForegroundColor Gray
                    Write-Host $secret -NoNewline -ForegroundColor Yellow
                    Write-Host '",' -ForegroundColor Gray
                    Write-Host '        "FPD_PROXY_PORT": "8081"' -ForegroundColor Gray
                    Write-Host '      }' -ForegroundColor Gray
                    Write-Host '    }' -ForegroundColor Gray
                    Write-Host '  }' -ForegroundColor Gray
                    Write-Host '}' -ForegroundColor Gray
                }
                "*PFW*" {
                    Write-Host '{' -ForegroundColor Gray
                    Write-Host '  "mcpServers": {' -ForegroundColor Gray
                    Write-Host '    "uspto_pfw": {' -ForegroundColor Gray
                    Write-Host '      "command": "C:/Users/YOUR_USERNAME/uspto_pfw_mcp/.venv/Scripts/python.exe",' -ForegroundColor Gray
                    Write-Host '      "args": ["-m", "patent_filewrapper_mcp.main"],' -ForegroundColor Gray
                    Write-Host '      "cwd": "C:/Users/YOUR_USERNAME/uspto_pfw_mcp",' -ForegroundColor Gray
                    Write-Host '      "env": {' -ForegroundColor Gray
                    Write-Host '        "INTERNAL_AUTH_SECRET": "' -NoNewline -ForegroundColor Gray
                    Write-Host $secret -NoNewline -ForegroundColor Yellow
                    Write-Host '",' -ForegroundColor Gray
                    Write-Host '        "PFW_PROXY_PORT": "8080"' -ForegroundColor Gray
                    Write-Host '      }' -ForegroundColor Gray
                    Write-Host '    }' -ForegroundColor Gray
                    Write-Host '  }' -ForegroundColor Gray
                    Write-Host '}' -ForegroundColor Gray
                }
                "*PTAB*" {
                    Write-Host '{' -ForegroundColor Gray
                    Write-Host '  "mcpServers": {' -ForegroundColor Gray
                    Write-Host '    "uspto_ptab": {' -ForegroundColor Gray
                    Write-Host '      "command": "C:/Users/YOUR_USERNAME/uspto_ptab_mcp/.venv/Scripts/python.exe",' -ForegroundColor Gray
                    Write-Host '      "args": ["-m", "ptab_mcp.main"],' -ForegroundColor Gray
                    Write-Host '      "cwd": "C:/Users/YOUR_USERNAME/uspto_ptab_mcp",' -ForegroundColor Gray
                    Write-Host '      "env": {' -ForegroundColor Gray
                    Write-Host '        "INTERNAL_AUTH_SECRET": "' -NoNewline -ForegroundColor Gray
                    Write-Host $secret -NoNewline -ForegroundColor Yellow
                    Write-Host '"' -ForegroundColor Gray
                    Write-Host '      }' -ForegroundColor Gray
                    Write-Host '    }' -ForegroundColor Gray
                    Write-Host '  }' -ForegroundColor Gray
                    Write-Host '}' -ForegroundColor Gray
                }
                "*Citations*" {
                    Write-Host '{' -ForegroundColor Gray
                    Write-Host '  "mcpServers": {' -ForegroundColor Gray
                    Write-Host '    "uspto_enriched_citations": {' -ForegroundColor Gray
                    Write-Host '      "command": "C:/Users/YOUR_USERNAME/uspto_enriched_citation_mcp/.venv/Scripts/python.exe",' -ForegroundColor Gray
                    Write-Host '      "args": ["-m", "uspto_enriched_citation_mcp.main"],' -ForegroundColor Gray
                    Write-Host '      "cwd": "C:/Users/YOUR_USERNAME/uspto_enriched_citation_mcp",' -ForegroundColor Gray
                    Write-Host '      "env": {' -ForegroundColor Gray
                    Write-Host '        "INTERNAL_AUTH_SECRET": "' -NoNewline -ForegroundColor Gray
                    Write-Host $secret -NoNewline -ForegroundColor Yellow
                    Write-Host '"' -ForegroundColor Gray
                    Write-Host '      }' -ForegroundColor Gray
                    Write-Host '    }' -ForegroundColor Gray
                    Write-Host '  }' -ForegroundColor Gray
                    Write-Host '}' -ForegroundColor Gray
                }
            }

            Write-Host ""
            Write-Host "Notes:" -ForegroundColor Cyan
            Write-Host "  - DPAPI Mode: API keys NOT in config (loaded from encrypted DPAPI storage)" -ForegroundColor Gray
            Write-Host "  - INTERNAL_AUTH_SECRET IS required in config to authenticate cross-MCP calls" -ForegroundColor Yellow
            Write-Host "  - Traditional Mode: Secret NOT needed (keys already plain text in config)" -ForegroundColor Gray
            Write-Host "  - Use SAME secret value across all 4 USPTO MCPs for inter-MCP communication" -ForegroundColor Gray
            Write-Host ""
            Write-Host "[TIP] Copy this JSON if you are using Secure Python DPAPI (recommended) method and need to manually restore your Claude Desktop config!" -ForegroundColor Cyan
        }
        else {
            Write-Host "[ERROR] Unable to retrieve INTERNAL_AUTH_SECRET" -ForegroundColor Red
        }

    } catch {
        Write-Host "[ERROR] Failed to retrieve INTERNAL_AUTH_SECRET: $_" -ForegroundColor Red
    }
}

# Function to show MCP-specific key requirements
function Show-KeyRequirements {
    $mcpType = Get-McpType

    Write-Host ""
    Write-Host "API Key Requirements for $mcpType" -ForegroundColor Cyan
    Write-Host ("=" * (25 + $mcpType.Length)) -ForegroundColor Cyan

    switch -Wildcard ($mcpType) {
        "*FPD*" {
            Write-Host "USPTO API Key:   [REQUIRED] For accessing Final Petition Decisions API" -ForegroundColor Green
            Write-Host "Mistral API Key: [OPTIONAL] For OCR on scanned documents" -ForegroundColor Yellow
        }
        "*PFW*" {
            Write-Host "USPTO API Key:   [REQUIRED] For accessing Patent File Wrapper API" -ForegroundColor Green
            Write-Host "Mistral API Key: [OPTIONAL] For OCR on scanned documents" -ForegroundColor Yellow
        }
        "*PTAB*" {
            Write-Host "USPTO API Key:   [REQUIRED] For accessing Open Data Portal PTAB API" -ForegroundColor Green
            Write-Host "Mistral API Key: [OPTIONAL] For OCR on scanned documents" -ForegroundColor Yellow
        }
        "*Citations*" {
            Write-Host "USPTO API Key:   [REQUIRED] For accessing Enriched Citations API" -ForegroundColor Green
            Write-Host "Mistral API Key: [OPTIONAL] Not used by Citations MCP" -ForegroundColor Yellow
        }
        default {
            Write-Host "Unable to determine MCP-specific requirements" -ForegroundColor Yellow
        }
    }
}

# Main script
function Main {
    # Check requirements
    if (-not (Test-Requirements)) {
        exit 1
    }

    $mcpType = Get-McpType

    while ($true) {
        # Clear screen and show header
        Clear-Host
        Write-Host "USPTO MCP API Key Management" -ForegroundColor Cyan
        Write-Host "============================" -ForegroundColor Cyan
        Write-Host "MCP Type: $mcpType" -ForegroundColor Yellow
        Write-Host ""

        # Get current API key status
        $keys = Get-ApiKeyStatus

        if ($keys) {
            Write-Host "Current API Keys:" -ForegroundColor White
            $usptoDisplay = if ($keys.USPTO) { Hide-ApiKey -ApiKey $keys.USPTO } else { "[Not set]" }
            $mistralDisplay = if ($keys.Mistral) { Hide-ApiKey -ApiKey $keys.Mistral } else { "[Not set]" }
            Write-Host "  USPTO API Key:   $usptoDisplay" -ForegroundColor $(if ($keys.USPTO) { "Green" } else { "Red" })
            Write-Host "  Mistral API Key: $mistralDisplay" -ForegroundColor $(if ($keys.Mistral) { "Green" } else { "Yellow" })
        } else {
            Write-Host "Unable to check current API key status" -ForegroundColor Red
        }

        Write-Host ""
        Write-Host "Actions:" -ForegroundColor White
        Write-Host "  [1] Update USPTO API key"
        Write-Host "  [2] Update Mistral API key"
        Write-Host "  [3] Remove API key(s)"
        Write-Host "  [4] Test API key functionality"
        Write-Host "  [5] View INTERNAL_AUTH_SECRET (for manual config)"
        Write-Host "  [6] Show key requirements"
        Write-Host "  [7] Exit"
        Write-Host ""

        $choice = Read-Host "Enter choice (1-7)"

        switch ($choice) {
            "1" {
                Write-Host ""
                Write-Host "Update USPTO API Key" -ForegroundColor Cyan
                Write-Host "====================" -ForegroundColor Cyan
                Write-Host ""

                # Use helper function with built-in validation and retry logic
                $newKey = Read-UsptoApiKeyWithValidation

                if ($newKey) {
                    Set-ApiKey -KeyType "USPTO" -ApiKey $newKey
                } else {
                    Write-Host "[INFO] Operation cancelled - no valid key provided" -ForegroundColor Yellow
                }

                Write-Host ""
                Read-Host "Press Enter to continue"
            }

            "2" {
                Write-Host ""
                Write-Host "Update Mistral API Key" -ForegroundColor Cyan
                Write-Host "======================" -ForegroundColor Cyan
                Write-Host ""

                # Use helper function with built-in validation and retry logic
                $newKey = Read-MistralApiKeyWithValidation

                if ($newKey -and $newKey -ne "") {
                    Set-ApiKey -KeyType "Mistral" -ApiKey $newKey
                } elseif ($null -eq $newKey) {
                    Write-Host "[ERROR] Validation failed after 3 attempts" -ForegroundColor Red
                } else {
                    Write-Host "[INFO] Operation cancelled - no key provided" -ForegroundColor Yellow
                }

                Write-Host ""
                Read-Host "Press Enter to continue"
            }

            "3" {
                Write-Host ""
                Write-Host "Remove API Key(s)" -ForegroundColor Cyan
                Write-Host "=================" -ForegroundColor Cyan
                Write-Host "  [1] Remove USPTO API key only"
                Write-Host "  [2] Remove Mistral API key only"
                Write-Host "  [3] Remove ALL API keys"
                Write-Host "  [4] Cancel"
                Write-Host ""

                $removeChoice = Read-Host "Enter choice (1-4)"

                switch ($removeChoice) {
                    "1" { Remove-ApiKeys -USPTO }
                    "2" { Remove-ApiKeys -Mistral }
                    "3" {
                        $confirm = Read-Host "Are you sure you want to remove ALL API keys? (y/N)"
                        if ($confirm -eq "y" -or $confirm -eq "Y") {
                            Remove-ApiKeys -All
                        } else {
                            Write-Host "[INFO] Operation cancelled" -ForegroundColor Yellow
                        }
                    }
                    "4" { Write-Host "[INFO] Operation cancelled" -ForegroundColor Yellow }
                    default { Write-Host "[ERROR] Invalid choice" -ForegroundColor Red }
                }

                Write-Host ""
                Read-Host "Press Enter to continue"
            }

            "4" {
                Test-ApiKeys
                Write-Host ""
                Read-Host "Press Enter to continue"
            }

            "5" {
                Show-InternalAuthSecret
                Write-Host ""
                Read-Host "Press Enter to continue"
            }

            "6" {
                Show-KeyRequirements
                Write-Host ""
                Read-Host "Press Enter to continue"
            }

            "7" {
                Write-Host ""
                Write-Host "Goodbye!" -ForegroundColor Green
                exit 0
            }

            default {
                Write-Host ""
                Write-Host "[ERROR] Invalid choice. Please enter 1-7." -ForegroundColor Red
                Start-Sleep -Seconds 2
            }
        }
    }
}

# Run the main function
Main
