# Windows Deployment Script for USPTO Enriched Citations MCP
# PowerShell version - Unified API Key Management

Write-Host "=== USPTO Enriched Citations MCP - Windows Setup ===" -ForegroundColor Green

# Get project directory
$ProjectDir = Get-Location

# Import validation helpers module
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module "$ScriptDir\Validation-Helpers.psm1" -Force

# Unified secure storage functions
function Set-UnifiedUsptoKey {
    param([string]$ApiKey)

    try {
        Set-Location $ProjectDir

        # SECURITY: Pass API key via environment variable to prevent command injection
        # DO NOT use string interpolation with user input!
        $env:TEMP_API_KEY_STORAGE = $ApiKey

        $result = uv run python -c "
import sys
import os
sys.path.insert(0, 'src')
from uspto_enriched_citation_mcp.shared_secure_storage import store_uspto_api_key

# Read API key from environment variable (secure)
api_key = os.environ.get('TEMP_API_KEY_STORAGE', '')
if not api_key:
    print('FAILED')
    sys.exit(1)

success = store_uspto_api_key(api_key)
print('SUCCESS' if success else 'FAILED')
" 2>&1 | Out-String

        # Clean up environment variable immediately
        Remove-Item Env:\TEMP_API_KEY_STORAGE -ErrorAction SilentlyContinue

        if ($result.Trim() -eq "SUCCESS") {
            Write-Host "[OK] USPTO API key stored in unified secure storage" -ForegroundColor Green
            Write-Host "     Location: ~/.uspto_api_key (DPAPI encrypted)" -ForegroundColor Yellow
            return $true
        } else {
            Write-Host "[ERROR] Failed to store USPTO API key" -ForegroundColor Red
            return $false
        }
    }
    catch {
        # Ensure cleanup even on error
        Remove-Item Env:\TEMP_API_KEY_STORAGE -ErrorAction SilentlyContinue
        Write-Host "[ERROR] Failed to store USPTO API key: $_" -ForegroundColor Red
        return $false
    }
}

function Set-UnifiedMistralKey {
    param([string]$ApiKey)

    try {
        Set-Location $ProjectDir

        # SECURITY: Pass API key via environment variable to prevent command injection
        $env:TEMP_API_KEY_STORAGE = $ApiKey

        $result = uv run python -c "
import sys
import os
sys.path.insert(0, 'src')
from uspto_enriched_citation_mcp.shared_secure_storage import store_mistral_api_key

# Read API key from environment variable (secure)
api_key = os.environ.get('TEMP_API_KEY_STORAGE', '')
if not api_key:
    print('FAILED')
    sys.exit(1)

success = store_mistral_api_key(api_key)
print('SUCCESS' if success else 'FAILED')
" 2>&1 | Out-String

        # Clean up environment variable immediately
        Remove-Item Env:\TEMP_API_KEY_STORAGE -ErrorAction SilentlyContinue

        if ($result.Trim() -eq "SUCCESS") {
            Write-Host "[OK] Mistral API key stored in unified secure storage" -ForegroundColor Green
            Write-Host "     Location: ~/.mistral_api_key (DPAPI encrypted)" -ForegroundColor Yellow
            return $true
        } else {
            Write-Host "[ERROR] Failed to store Mistral API key" -ForegroundColor Red
            return $false
        }
    }
    catch {
        # Ensure cleanup even on error
        Remove-Item Env:\TEMP_API_KEY_STORAGE -ErrorAction SilentlyContinue
        Write-Host "[ERROR] Failed to store Mistral API key: $_" -ForegroundColor Red
        return $false
    }
}

function Test-UnifiedKeys {
    try {
        Set-Location $ProjectDir
        
        # Use here-string for proper Python code formatting
        $pythonCode = @'
import sys
sys.path.insert(0, 'src')
try:
    from uspto_enriched_citation_mcp.shared_secure_storage import get_uspto_api_key, get_mistral_api_key
    uspto_key = get_uspto_api_key()
    mistral_key = get_mistral_api_key()
    print('USPTO:YES' if uspto_key and len(uspto_key) >= 10 else 'USPTO:NO')
    print('MISTRAL:YES' if mistral_key and len(mistral_key) >= 10 else 'MISTRAL:NO')
except Exception as e:
    print('USPTO:NO')
    print('MISTRAL:NO')
'@
        
        $result = uv run python -c $pythonCode 2>&1 | Out-String

        $lines = $result -split "`n" | Where-Object { $_.Trim() -ne "" }
        $usptoFound = $false
        $mistralFound = $false
        
        foreach ($line in $lines) {
            if ($line -match "USPTO:(YES|NO)") {
                $usptoFound = ($matches[1] -eq "YES")
            }
            if ($line -match "MISTRAL:(YES|NO)") {
                $mistralFound = ($matches[1] -eq "YES")
            }
        }
        
        return @{
            "USPTO" = $usptoFound
            "MISTRAL" = $mistralFound
        }
    }
    catch {
        return @{
            "USPTO" = $false
            "MISTRAL" = $false
        }
    }
}

# Check if uv is installed, install if not
Write-Host "[INFO] Python NOT required - uv will manage Python automatically" -ForegroundColor Cyan
Write-Host ""
try {
    $uvVersion = uv --version 2>$null
    Write-Host "[OK] uv found: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "[INFO] uv not found. Installing uv..." -ForegroundColor Yellow

    # Try winget first (preferred method)
    try {
        winget install --id=astral-sh.uv -e
        Write-Host "[OK] uv installed via winget" -ForegroundColor Green
    } catch {
        Write-Host "[INFO] winget failed, trying PowerShell install method..." -ForegroundColor Yellow
        try {
            powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
            Write-Host "[OK] uv installed via PowerShell script" -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Failed to install uv. Please install manually:" -ForegroundColor Red
            Write-Host "   winget install --id=astral-sh.uv -e" -ForegroundColor Yellow
            Write-Host "   OR visit: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
            exit 1
        }
    }

    # Refresh PATH for current session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")

    # Add uv's typical installation paths if not already in PATH
    $uvPaths = @(
        "$env:USERPROFILE\.cargo\bin",           # cargo install location
        "$env:LOCALAPPDATA\Programs\uv\bin",      # winget install location
        "$env:APPDATA\uv\bin"                     # alternative location
    )

    foreach ($uvPath in $uvPaths) {
        if (Test-Path $uvPath) {
            if ($env:PATH -notlike "*$uvPath*") {
                $env:PATH = "$uvPath;$env:PATH"
                Write-Host "[INFO] Added $uvPath to PATH" -ForegroundColor Yellow
            }
        }
    }

    # Verify uv is now accessible
    try {
        $uvVersion = uv --version 2>$null
        Write-Host "[OK] uv is now accessible: $uvVersion" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] uv installed but not accessible. Please restart PowerShell and run script again." -ForegroundColor Red
        Write-Host "[INFO] Or manually add uv to PATH and continue." -ForegroundColor Yellow
        exit 1
    }
}

# Install dependencies with uv
Write-Host "[INFO] Installing dependencies with uv..." -ForegroundColor Yellow

# Force uv to use prebuilt wheels (avoid Rust compilation)
Write-Host "[INFO] Installing dependencies with prebuilt wheels (Python 3.12)..." -ForegroundColor Yellow

try {
    # Use Python 3.12 which has guaranteed prebuilt wheels for all dependencies
    # Python 3.14 is too new and doesn't have wheels yet
    uv sync --python 3.12
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Verify installation
Write-Host "[INFO] Verifying installation..." -ForegroundColor Yellow
try {
    $commandCheck = Get-Command uspto-enriched-citation-mcp -ErrorAction SilentlyContinue
    if ($commandCheck) {
        Write-Host "[OK] Command available: $($commandCheck.Source)" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Warning: Command verification failed - check PATH" -ForegroundColor Yellow
        Write-Host "[INFO] You can run the server with: uv run uspto-enriched-citation-mcp" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARN] Warning: Command verification failed - check PATH" -ForegroundColor Yellow
    Write-Host "[INFO] You can run the server with: uv run uspto-enriched-citation-mcp" -ForegroundColor Yellow
}

# API Key Configuration with Unified Storage
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "SECURE API KEY CONFIGURATION" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API keys will be stored in DPAPI encrypted storage" -ForegroundColor Yellow
Write-Host "Location: ~/.uspto_api_key" -ForegroundColor Yellow
Write-Host "Encryption: Windows Data Protection API (user + machine specific)" -ForegroundColor Yellow
Write-Host ""

# Step 1: Check for existing keys first
Write-Host "[INFO] Checking for existing API keys in secure storage..." -ForegroundColor Yellow
$existingKeys = Test-UnifiedKeys

# Flags for tracking configuration path
$usingPreexistingDPAPI = $false
$newKeyAsEnv = $false
$finalConfigMethod = "none"  # Track final config method: "dpapi", "traditional", or "none"

if ($existingKeys.USPTO) {
    # Step 2: Ask user to use existing or update
    Write-Host "[OK] USPTO API key found in encrypted storage" -ForegroundColor Green
    Write-Host "[INFO] Configuration: [1] Use existing key [2] Update key" -ForegroundColor Cyan
    $keyChoice = Read-Host "Enter choice (1 or 2, default is 1)"

    if ($keyChoice -eq "2") {
        $updateKeys = $true
    } else {
        $updateKeys = $false
        $usingPreexistingDPAPI = $true  # Flag: Using existing DPAPI key
        Write-Host "[OK] Using existing encrypted USPTO API key" -ForegroundColor Green
    }
} else {
    Write-Host "[INFO] No USPTO API key found in encrypted storage" -ForegroundColor Yellow
    Write-Host "[INFO] USPTO API key is REQUIRED for Citations MCP" -ForegroundColor Yellow
    $updateKeys = $true
}

# Step 3: Collect and store keys if needed
if ($updateKeys -eq $true) {
    # Show API key format requirements
    Show-ApiKeyRequirements

    # Collect and validate USPTO API key (required)
    $usptoApiKey = Read-UsptoApiKeyWithValidation
    if ($usptoApiKey -eq $null) {
        Write-Host "[ERROR] Failed to obtain valid USPTO API key" -ForegroundColor Red
        exit 1
    }

    # Store keys in unified storage
    Write-Host ""
    Write-Host "[INFO] Storing API key in unified secure storage..." -ForegroundColor Yellow

    if (Set-UnifiedUsptoKey -ApiKey $usptoApiKey) {
        Write-Host "[OK] USPTO API key stored in unified storage" -ForegroundColor Green
        $newKeyAsEnv = $true  # Flag: New key was entered and stored
    } else {
        Write-Host "[ERROR] Failed to store USPTO API key" -ForegroundColor Red
        exit 1
    }

    # Clear sensitive variables from memory
    $usptoApiKey = $null
    [System.GC]::Collect()

    if ($newKeyAsEnv) {
        Write-Host ""
        Write-Host "[OK] Unified storage benefits:" -ForegroundColor Cyan
        Write-Host "     - Single-key-per-file architecture" -ForegroundColor White
        Write-Host "     - DPAPI encryption (user + machine specific)" -ForegroundColor White
        Write-Host "     - Shared across all USPTO MCPs (FPD/PFW/PTAB/Citations)" -ForegroundColor White
        Write-Host "     - File: ~/.uspto_api_key" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "# No Mistral API key needed for Citations MCP (no documents to process)" -ForegroundColor Gray

# Get current directory and convert backslashes to forward slashes
$CurrentDir = (Get-Location).Path -replace "\\","/"

# Generate secure INTERNAL_AUTH_SECRET using unified storage
Write-Host ""
Write-Host "[INFO] Configuring shared INTERNAL_AUTH_SECRET..." -ForegroundColor Yellow

try {
    Set-Location $ProjectDir
    $pythonExe = "$ProjectDir/.venv/Scripts/python.exe"
    $pythonCode = @'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
from uspto_enriched_citation_mcp.shared_secure_storage import ensure_internal_auth_secret

# Get or create shared secret
secret = ensure_internal_auth_secret()
if secret:
    print(secret)
else:
    sys.exit(1)
'@

    $result = & $pythonExe -c $pythonCode 2>&1 | Out-String
    $lines = $result -split "`n" | Where-Object { $_.Trim() -ne "" }

    # The first non-INFO line should be the secret
    $internalSecret = ""
    foreach ($line in $lines) {
        if ($line -notmatch "^(INFO|DEBUG|WARNING|ERROR):" -and $line.Trim() -ne "") {
            $internalSecret = $line.Trim()
            break
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($internalSecret)) {
        # Check if this was a newly generated secret or existing one
        if ($result -match "Generating new internal auth secret") {
            Write-Host "[OK] Generated new INTERNAL_AUTH_SECRET (first USPTO MCP installation)" -ForegroundColor Green
            Write-Host "     Location: ~/.uspto_internal_auth_secret (DPAPI encrypted)" -ForegroundColor Yellow
            Write-Host "     This secret will be SHARED across all USPTO MCPs (FPD/PFW/PTAB/Citations)" -ForegroundColor Yellow
        } else {
            Write-Host "[OK] Using existing INTERNAL_AUTH_SECRET from unified storage" -ForegroundColor Green
            Write-Host "     Location: ~/.uspto_internal_auth_secret (DPAPI encrypted)" -ForegroundColor Yellow
            Write-Host "     Shared with other installed USPTO MCPs" -ForegroundColor Yellow
        }
        Write-Host "     This secret authenticates internal MCP communication" -ForegroundColor Yellow
    } else {
        Write-Host "[ERROR] Failed to get or generate INTERNAL_AUTH_SECRET" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "[ERROR] Failed to configure INTERNAL_AUTH_SECRET: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Ask about Claude Desktop configuration
Write-Host ""
Write-Host "Claude Desktop Configuration" -ForegroundColor Cyan
Write-Host ""

$configureClaudeDesktop = Read-Host "Would you like to configure Claude Desktop integration? (Y/n)"
if ($configureClaudeDesktop -eq "" -or $configureClaudeDesktop -eq "Y" -or $configureClaudeDesktop -eq "y") {

    # Step 5 & 6: Determine configuration method based on flags
    $useSecureStorage = $false
    $configureUsptoApiKey = ""

    if ($usingPreexistingDPAPI -and -not $newKeyAsEnv) {
        # Step 5: User is using existing DPAPI key → Auto-configure as DPAPI
        Write-Host ""
        Write-Host "[OK] Using DPAPI encrypted storage (secure)" -ForegroundColor Green
        Write-Host "     API keys will be loaded automatically from encrypted storage" -ForegroundColor Yellow
        Write-Host "     No API keys will be stored in Claude Desktop config file" -ForegroundColor Yellow
        Write-Host ""
        $useSecureStorage = $true
        $finalConfigMethod = "dpapi"
    } elseif ($newKeyAsEnv) {
        # Step 6: User just entered a new key → Give choice between Secure and Traditional
        Write-Host ""
        Write-Host "Claude Desktop Configuration Method:" -ForegroundColor Cyan
        Write-Host "  [1] Secure Python DPAPI (recommended) - API keys loaded from encrypted storage" -ForegroundColor White
        Write-Host "  [2] Traditional - API keys stored in Claude Desktop config file" -ForegroundColor White
        Write-Host ""
        $configChoice = Read-Host "Enter choice (1 or 2, default is 1)"

        if ($configChoice -eq "2") {
            # Step 8: Traditional configuration
            Write-Host "[INFO] Using traditional method (API keys in config file)" -ForegroundColor Yellow
            $useSecureStorage = $false
            $finalConfigMethod = "traditional"

            # Retrieve the key from DPAPI storage for config file
            try {
                Set-Location $ProjectDir
                $pythonCode = @'
import sys
sys.path.insert(0, 'src')
from uspto_enriched_citation_mcp.shared_secure_storage import get_uspto_api_key
key = get_uspto_api_key()
if key:
    print(key)
'@
                $configureUsptoApiKey = uv run python -c $pythonCode 2>$null | Out-String
                $configureUsptoApiKey = $configureUsptoApiKey.Trim()
            }
            catch {
                $configureUsptoApiKey = ""
            }
        } else {
            # Step 7: Secure DPAPI configuration
            Write-Host "[OK] Using DPAPI encrypted storage (secure)" -ForegroundColor Green
            Write-Host "     API keys will be loaded automatically from encrypted storage" -ForegroundColor Yellow
            Write-Host "     No API keys will be stored in Claude Desktop config file" -ForegroundColor Yellow
            Write-Host ""
            $useSecureStorage = $true
            $finalConfigMethod = "dpapi"
        }
    } else {
        # No key configured → Default to DPAPI (no key to store)
        Write-Host ""
        Write-Host "[OK] Using DPAPI encrypted storage (secure)" -ForegroundColor Green
        Write-Host "     No API keys configured" -ForegroundColor Yellow
        Write-Host ""
        $useSecureStorage = $true
        $finalConfigMethod = "dpapi"
    }

    # Function to generate env section based on configuration choice
    function Get-EnvSection {
        param($indent = "        ")

        $envItems = @()

        if ($useSecureStorage) {
            # Secure storage - no API keys in config
            $envItems += "$indent`"INTERNAL_AUTH_SECRET`": `"$internalSecret`""
        } else {
            # Traditional - API keys in config
            if ($configureUsptoApiKey) { $envItems += "$indent`"USPTO_API_KEY`": `"$configureUsptoApiKey`"" }
            $envItems += "$indent`"INTERNAL_AUTH_SECRET`": `"$internalSecret`""
        }

        return $envItems -join ",`n"
    }
    
    # Function to generate server JSON entry
    function Get-ServerJson {
        param($indent = "    ")
        
        $envSection = Get-EnvSection -indent "      "
        
        return @"
$indent"uspto_enriched_citations": {
$indent  "command": "$CurrentDir/.venv/Scripts/python.exe",
$indent  "args": [
$indent    "-m",
$indent    "uspto_enriched_citation_mcp.main"
$indent  ],
$indent  "cwd": "$CurrentDir",
$indent  "env": {
$envSection
$indent  }
$indent}
"@
    }

    # Claude Desktop config location
    $ClaudeConfigDir = "$env:APPDATA\Claude"
    $ClaudeConfigFile = "$ClaudeConfigDir\claude_desktop_config.json"

    Write-Host "[INFO] Claude Desktop config location: $ClaudeConfigFile" -ForegroundColor Yellow

    if (Test-Path $ClaudeConfigFile) {
        Write-Host "[INFO] Existing Claude Desktop config found" -ForegroundColor Yellow
        Write-Host "[INFO] Merging Enriched Citations MCP configuration with existing config..." -ForegroundColor Yellow

        try {
            # Read existing config as raw text
            $existingJsonText = Get-Content $ClaudeConfigFile -Raw

            # Backup the original file
            $backupFile = "$ClaudeConfigFile.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
            Copy-Item $ClaudeConfigFile $backupFile
            Write-Host "[INFO] Backup created: $backupFile" -ForegroundColor Yellow

            # Try to parse JSON, with better error handling for malformed JSON
            try {
                $existingConfig = $existingJsonText | ConvertFrom-Json
            } catch {
                Write-Host "[ERROR] Existing Claude Desktop config has JSON syntax errors" -ForegroundColor Red
                Write-Host "[ERROR] Common issue: Missing comma after closing braces '}' between MCP server sections" -ForegroundColor Red
                Write-Host "[INFO] Please fix the JSON syntax and run the setup script again" -ForegroundColor Yellow
                Write-Host "[INFO] Your backup is saved at: $backupFile" -ForegroundColor Yellow
                Write-Host ""
                Write-Host "Quick fix: Look for lines like this pattern and add missing commas:" -ForegroundColor Yellow
                Write-Host "    }" -ForegroundColor White
                Write-Host "    `"next_server`": {" -ForegroundColor White
                Write-Host ""
                Write-Host "Should be:" -ForegroundColor Yellow
                Write-Host "    }," -ForegroundColor Green
                Write-Host "    `"next_server`": {" -ForegroundColor White
                Write-Host ""
                exit 1
            }

            # Check if mcpServers exists, create if not
            if (-not $existingConfig.mcpServers) {
                # Empty config - create from scratch using unified secure storage
                $envSection = Get-EnvSection -indent "        "
                $jsonConfig = @"
{
  "mcpServers": {
    "uspto_enriched_citations": {
      "command": "$CurrentDir/.venv/Scripts/python.exe",
      "args": [
        "-m",
        "uspto_enriched_citation_mcp.main"
      ],
      "cwd": "$CurrentDir",
      "env": {
$envSection
      }
    }
  }
}
"@
            } else {
                # Has existing servers - need to merge manually
                # Build the uspto_enriched_citations section using unified secure storage
                $envSection = Get-EnvSection -indent "        "
                $citationsJson = @"
    "uspto_enriched_citations": {
      "command": "$CurrentDir/.venv/Scripts/python.exe",
      "args": [
        "-m",
        "uspto_enriched_citation_mcp.main"
      ],
      "cwd": "$CurrentDir",
      "env": {
$envSection
      }
    }
"@

                # Get all existing server names
                $existingServers = $existingConfig.mcpServers.PSObject.Properties.Name

                # Build the mcpServers object with all servers
                $serverEntries = @()

                foreach ($serverName in $existingServers) {
                    if ($serverName -ne "uspto_enriched_citations") {
                        # Convert to JSON without compression for readability
                        $serverJson = $existingConfig.mcpServers.$serverName | ConvertTo-Json -Depth 10

                        # Split into lines and format properly
                        $jsonLines = $serverJson -split "`n"

                        # First line: "serverName": {
                        $formattedEntry = "    `"$serverName`": $($jsonLines[0])"

                        # Remaining lines: indent by 4 spaces
                        for ($i = 1; $i -lt $jsonLines.Length; $i++) {
                            $formattedEntry += "`n    $($jsonLines[$i])"
                        }

                        # Add the formatted server entry
                        $serverEntries += $formattedEntry
                    }
                }

                # Add uspto_enriched_citations
                $serverEntries += $citationsJson.TrimEnd()

                $allServers = $serverEntries -join ",`n"

                $jsonConfig = @"
{
  "mcpServers": {
$allServers
  }
}
"@
            }

            # Write with UTF8 without BOM
            $utf8NoBom = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($ClaudeConfigFile, $jsonConfig, $utf8NoBom)

            Write-Host "[OK] Successfully merged Enriched Citations MCP configuration!" -ForegroundColor Green
            Write-Host "[OK] Your existing MCP servers have been preserved" -ForegroundColor Green
            if ($useSecureStorage) {
                Write-Host "[INFO] API keys are NOT in config file (loaded from encrypted storage)" -ForegroundColor Yellow
            } else {
                Write-Host "[INFO] API keys are stored in config file (traditional method)" -ForegroundColor Yellow
            }
            Write-Host "[INFO] Configuration backup saved at: $backupFile" -ForegroundColor Yellow

        } catch {
            Write-Host "[ERROR] Failed to merge configuration: $_" -ForegroundColor Red
            Write-Host "[ERROR] Details: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please manually add this configuration to: $ClaudeConfigFile" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Add this to your mcpServers section:" -ForegroundColor White

            # Manual JSON string for display
            $manualJson = Get-ServerJson -indent ""
            Write-Host $manualJson -ForegroundColor Cyan
            Write-Host ""
            if (Test-Path $backupFile) {
                Write-Host "Your backup is saved at: $backupFile" -ForegroundColor Yellow
            }
            exit 1
        }

    } else {
        # Create new config file
        Write-Host "[INFO] Creating new Claude Desktop config..." -ForegroundColor Yellow

        # Create directory if it doesn't exist
        if (-not (Test-Path $ClaudeConfigDir)) {
            New-Item -ItemType Directory -Path $ClaudeConfigDir -Force | Out-Null
        }

        # Create config
        $serverJson = Get-ServerJson
        $jsonConfig = @"
{
  "mcpServers": {
$serverJson
  }
}
"@
        # Write with UTF8 without BOM
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($ClaudeConfigFile, $jsonConfig, $utf8NoBom)

        Write-Host "[OK] Created new Claude Desktop config" -ForegroundColor Green
        if ($useSecureStorage) {
            Write-Host "[INFO] ✅ API keys are NOT in config file (loaded from encrypted storage)" -ForegroundColor Yellow
        } else {
            Write-Host "[INFO] API keys are stored in config file (traditional method)" -ForegroundColor Yellow
        }
    }

    Write-Host "[OK] Claude Desktop configuration complete!" -ForegroundColor Green
}

# Final summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Windows setup complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Please restart Claude Desktop to load the MCP server" -ForegroundColor Yellow
Write-Host ""

Write-Host "Configuration Summary:" -ForegroundColor Cyan
Write-Host ""

# Check final key status
$finalKeys = Test-UnifiedKeys
if ($finalKeys.USPTO) {
    Write-Host "  [OK] USPTO API Key: Stored in DPAPI encrypted storage" -ForegroundColor Green
    Write-Host "       Location: ~/.uspto_api_key (DPAPI encrypted)" -ForegroundColor Yellow
} else {
    Write-Host "  [WARN] USPTO API Key: Not found in unified storage (required)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  [OK] Storage Architecture: Single-key-per-file (shared across USPTO MCPs)" -ForegroundColor Green
Write-Host "  [OK] Installation Directory: $CurrentDir" -ForegroundColor Green
Write-Host ""

Write-Host "Security Features:" -ForegroundColor Cyan
if ($finalConfigMethod -eq "dpapi") {
    Write-Host "  [*] Configuration Method: DPAPI Encrypted Storage (Secure)" -ForegroundColor White
    Write-Host "  [*] API keys encrypted with Windows DPAPI (user and machine specific)" -ForegroundColor White
    Write-Host "  [*] API keys NOT in Claude Desktop config file" -ForegroundColor White
    Write-Host "  [*] API keys NOT visible in process list (environment variables used)" -ForegroundColor White
} elseif ($finalConfigMethod -eq "traditional") {
    Write-Host "  [*] Configuration Method: Traditional (API keys in config file)" -ForegroundColor White
    Write-Host "  [*] API keys stored in Claude Desktop config file" -ForegroundColor White
    Write-Host "  [*] API keys also backed up in DPAPI encrypted storage" -ForegroundColor White
} else {
    Write-Host "  [*] Configuration Method: Not configured" -ForegroundColor White
}
Write-Host "  [*] API key format validation (prevents typos)" -ForegroundColor White
Write-Host "  [*] Secure password input (API keys hidden during entry)" -ForegroundColor White
Write-Host "  [*] Memory cleanup after key entry (prevents leaks)" -ForegroundColor White
Write-Host ""

Write-Host "Available Tools (6):" -ForegroundColor Cyan
Write-Host "  - ec_search_citations_minimal (ultra-fast discovery)" -ForegroundColor White
Write-Host "  - ec_search_citations_balanced (detailed analysis)" -ForegroundColor White
Write-Host "  - ec_search_by_patent (patent-specific citations)" -ForegroundColor White
Write-Host "  - ec_search_by_examiner (examiner citation patterns)" -ForegroundColor White
Write-Host "  - ec_get_citation_details (full citation details)" -ForegroundColor White
Write-Host "  - ec_get_tool_reflections (workflow guidance)" -ForegroundColor White
Write-Host ""
Write-Host "Key Management:" -ForegroundColor Cyan
Write-Host "  Manage keys: ./deploy/manage_api_keys.ps1" -ForegroundColor Yellow  
Write-Host "  Test keys:   uv run python tests/test_unified_key_management.py" -ForegroundColor Yellow
Write-Host "  Cross-MCP:   Keys shared with FPD, PFW, and PTAB MCPs" -ForegroundColor White
Write-Host ""
Write-Host "Test with: ec_search_citations_minimal" -ForegroundColor Yellow
Write-Host "Learn workflows: ec_get_tool_reflections" -ForegroundColor Yellow