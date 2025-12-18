#!/bin/bash

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }

# Load validation helpers
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/validation-helpers.sh"

echo -e "${GREEN}=== USPTO Enriched Citation MCP - Linux Setup ===${NC}"
echo ""

# Get project directory for later use
PROJECT_DIR=$(pwd)

# Step 1: Check/Install uv
log_info "UV will handle Python installation automatically"

if ! command -v uv &> /dev/null; then
    log_info "uv not found. Installing uv package manager..."
    
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        # Add uv to PATH for current session
        export PATH="$HOME/.cargo/bin:$PATH"
        
        # Verify installation
        if command -v uv &> /dev/null; then
            UV_VERSION=$(uv --version)
            log_success "uv installed successfully: $UV_VERSION"
        else
            log_error "Failed to install uv. Please install manually:"
            echo -e "${YELLOW}   curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
            exit 1
        fi
    else
        log_error "Failed to install uv automatically"
        log_info "Please install uv manually and re-run this script"
        exit 1
    fi
else
    UV_VERSION=$(uv --version)
    log_info "uv found: $UV_VERSION"
fi

# Step 2: Install project dependencies
log_info "Installing project dependencies with uv..."

if uv sync; then
    log_success "Dependencies installed successfully"
else
    log_error "Failed to install dependencies"
    exit 1
fi

# Step 3: Install package in editable mode
log_info "Installing USPTO Enriched Citation MCP package..."

if uv pip install -e .; then
    log_success "Package installed successfully"
else
    log_error "Failed to install package"
    exit 1
fi

# Step 4: Verify installation
log_info "Verifying installation..."

if command -v uspto-enriched-citation-mcp &> /dev/null; then
    log_success "Command available: $(which uspto-enriched-citation-mcp)"
elif uv run python -c "import src.uspto_enriched_citation_mcp; print('Import successful')" &> /dev/null; then
    log_success "Package import successful - can run with: uv run uspto-enriched-citation-mcp"
else
    log_warning "Installation verification failed"
    log_info "You can run the server with: uv run uspto-enriched-citation-mcp"
fi

echo ""

# Step 5: API Key Configuration
echo -e "${GREEN}[INFO] API Key Configuration${NC}"
echo ""

log_info "USPTO Enriched Citation API uses the standard Data Services API"
log_info "Get your free API key from: https://data.uspto.gov/myodp/"
echo ""

# Prompt for USPTO API key with validation (uses secure hidden input)
USPTO_API_KEY=$(prompt_and_validate_uspto_key)
if [[ -z "$USPTO_API_KEY" ]]; then
    log_error "Failed to obtain valid USPTO API key"
    exit 1
fi

log_success "USPTO API key validated and configured"
echo ""

# Step 6: Store API keys in SECURE storage (NOT in config file!)
echo ""
log_info "Storing API keys in secure storage..."
log_info "Location: ~/.uspto_api_key (file permissions: 600)"
echo ""

# Store USPTO key using environment variable (more secure than command line)
export SETUP_USPTO_KEY="$USPTO_API_KEY"

STORE_RESULT=$(python3 << 'EOF'
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path.cwd() / 'src'))

try:
    from uspto_enriched_citation_mcp.shared_secure_storage import store_uspto_api_key

    # Read from environment variable (NOT from command line - more secure)
    api_key = os.environ.get('SETUP_USPTO_KEY', '')
    if not api_key:
        print('ERROR: No API key provided')
        sys.exit(1)

    if store_uspto_api_key(api_key):
        print('SUCCESS')
    else:
        print('ERROR: Failed to store USPTO key')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {str(e)}')
    sys.exit(1)
EOF
)

# Clear environment variable immediately
unset SETUP_USPTO_KEY

if [[ "$STORE_RESULT" == "SUCCESS" ]]; then
    log_success "USPTO API key stored in secure storage"
    log_info "    Location: ~/.uspto_api_key"
    log_info "    Permissions: 600 (owner read/write only)"

    # Verify file permissions
    if [ -f "$HOME/.uspto_api_key" ]; then
        PERMS=$(stat -c '%a' "$HOME/.uspto_api_key" 2>/dev/null || stat -f '%A' "$HOME/.uspto_api_key" 2>/dev/null)
        if [[ "$PERMS" == "600" ]]; then
            log_success "    Verified: File permissions are secure (600)"
        else
            log_warning "    Warning: File permissions are $PERMS (expected 600)"
            # Try to fix
            chmod 600 "$HOME/.uspto_api_key" 2>/dev/null || true
        fi
    fi
else
    log_error "Failed to store USPTO API key: $STORE_RESULT"
    exit 1
fi

# Step 7: Claude Code Configuration
echo ""
log_info "Claude Code Configuration"
echo ""

read -p "Would you like to configure Claude Code integration? (Y/n): " CONFIGURE_CLAUDE
CONFIGURE_CLAUDE=${CONFIGURE_CLAUDE:-Y}

if [[ "$CONFIGURE_CLAUDE" =~ ^[Yy]$ ]]; then
    # Claude Code config location (Linux) - NOT Claude Desktop (Windows/Mac only)
    CLAUDE_CONFIG_FILE="$HOME/.claude.json"

    log_info "Claude Code config location: $CLAUDE_CONFIG_FILE"

    # On Linux, ALWAYS use secure storage (file with 600 permissions)
    # No "traditional" method option - that's less secure
    USE_SECURE_STORAGE=true
    
    if [ -f "$CLAUDE_CONFIG_FILE" ]; then
        log_info "Existing Claude Desktop config found"
        log_info "Merging USPTO Citation configuration with existing config..."

        # Backup the original file
        BACKUP_FILE="${CLAUDE_CONFIG_FILE}.backup_$(date +%Y%m%d_%H%M%S)"
        cp "$CLAUDE_CONFIG_FILE" "$BACKUP_FILE"
        log_info "Backup created: $BACKUP_FILE"

        # Use Python to merge JSON configuration (API key NOT included - in secure storage)
        MERGE_SCRIPT="
import json
import sys

try:
    # Read existing config
    with open('$CLAUDE_CONFIG_FILE', 'r') as f:
        config = json.load(f)

    # Ensure mcpServers exists
    if 'mcpServers' not in config:
        config['mcpServers'] = {}

    # Add or update uspto_enriched_citations server
    # NOTE: API key is NOT in config - it's loaded from secure storage (~/.uspto_api_key)
    server_config = {
        'command': 'uv',
        'args': [
            '--directory',
            '$PROJECT_DIR',
            'run',
            'uspto-enriched-citation-mcp'
        ],
        'env': {
            'ECITATION_RATE_LIMIT': '100'
        }
    }

    config['mcpServers']['uspto_enriched_citations'] = server_config

    # Write merged config
    with open('$CLAUDE_CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)

    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"

        if echo "$MERGE_SCRIPT" | python3; then
            log_success "Successfully merged USPTO Citation configuration!"
            log_success "Your existing MCP servers have been preserved"
        else
            log_error "Failed to merge config"
            log_info "Please manually add the configuration to $CLAUDE_CONFIG_FILE"
            exit 1
        fi

    else
        # Create new config file using Python for safe JSON generation
        log_info "Creating new Claude Desktop config..."

        CREATE_CONFIG_SCRIPT="
import json
import sys

try:
    # NOTE: API key is NOT in config - it's loaded from secure storage (~/.uspto_api_key)
    config = {
        'mcpServers': {
            'uspto_enriched_citations': {
                'command': 'uv',
                'args': [
                    '--directory',
                    '$PROJECT_DIR',
                    'run',
                    'uspto-enriched-citation-mcp'
                ],
                'env': {
                    'ECITATION_RATE_LIMIT': '100'
                }
            }
        }
    }

    # Write config file
    with open('$CLAUDE_CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)

    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"

        if echo "$CREATE_CONFIG_SCRIPT" | python3; then
            log_success "Created new Claude Desktop config"
        else
            log_error "Failed to create config file"
            exit 1
        fi
    fi

    # SECURITY FIX: Set restrictive file permissions on config file
    if [ -f "$CLAUDE_CONFIG_FILE" ]; then
        set_secure_file_permissions "$CLAUDE_CONFIG_FILE"
    fi

    log_success "Claude Code configuration complete!"

    # Display configuration method used
    echo ""
    log_success "Security Configuration:"
    log_info "  - API key stored in secure storage: ~/.uspto_api_key"
    log_info "  - File permissions: 600 (owner read/write only)"
    log_info "  - API key NOT in Claude Desktop config file"
    log_info "  - Shared storage across all USPTO MCPs (PFW/PTAB/FPD/Citations)"
else
    log_info "Skipping Claude Code configuration"
    log_info "You can manually configure later by editing ~/.claude.json"
    log_info "See README.md for configuration template"
fi

echo ""

# Step 8: Final Summary
echo -e "${GREEN}[OK] Linux setup complete!${NC}"
log_warning "Please restart Claude Code to load the MCP server"

echo ""
log_info "Configuration Summary:"
log_success "USPTO API Key: Stored in secure storage (~/.uspto_api_key)"
log_success "Dependencies: Installed"
log_success "Package: Available as command"
log_success "Installation Directory: $PROJECT_DIR"
log_success "Security: File permissions 600 (owner only)"

echo ""
log_info "Test the server:"
echo "  uv run uspto-enriched-citation-mcp --help"

echo ""
log_info "Test with Claude Code:"
echo "  Ask Claude: 'Use search_citations_minimal to find citations for art unit 2854'"
echo "  Ask Claude: 'Use get_available_fields to explore citation data fields'"
echo "  Ask Claude: 'Use validate_query to check Lucene syntax for patent searches'"

echo ""
log_info "Verify MCP is running:"
echo "  claude mcp list"

echo ""
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo ""