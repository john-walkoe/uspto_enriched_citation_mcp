# USPTO Enriched Citation API v3 MCP Server

A high-performance Model Context Protocol (MCP) server for USPTO Enriched Citation API v3 with **token-saving context reduction** capabilities (90-95%), **progressive disclosure workflows**, and **seamless cross-MCP integration** for complete patent lifecycle analysis.

[![Platform Support](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)]()
[![API](https://img.shields.io/badge/API-USPTO%20Enriched%20Citation%20v3-green.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[📥 Installation Guide](INSTALL.md)** | Complete cross-platform setup with automated scripts |
| **[🔑 API Key Guide](API_KEY_GUIDE.md)** | Step-by-step guide with screenshots for obtaining USPTO and Mistral API keys |
| **[📖 Usage Examples](USAGE_EXAMPLES.md)** | Function examples, workflows, and integration patterns |
| **[🎯 Prompt Templates](PROMPTS.md)** | Detailed guide to sophisticated prompt templates for citation analysis & research workflows |
| **[🧪 Testing Guide](tests/README.md)** | Test suite documentation and API key setup |
| **[🔒 Security Guidelines](SECURITY_GUIDELINES.md)** | Comprehensive security best practices |
| **[🛡️ Security Scanning](SECURITY_SCANNING.md)** | Automated secret detection and prevention guide |
| **[⚖️ License](LICENSE)** | MIT License terms and conditions |

## ⚡ Quick Start

### Windows Install

**Run PowerShell as Administrator**, then:

```powershell
# Navigate to your user profile
cd $env:USERPROFILE

# If git is installed:
git clone https://github.com/john-walkoe/uspto_enriched_citation_mcp.git
cd uspto_enriched_citation_mcp

# If git is NOT installed:
# Download and extract the repository to C:\Users\YOUR_USERNAME\uspto_enriched_citation_mcp
# Then navigate to the folder:
# cd C:\Users\YOUR_USERNAME\uspto_enriched_citation_mcp

# Run setup script (sets execution policy for this session only):
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process
.\deploy\windows_setup.ps1

# View INSTALL.md for sample script output.
# Close PowerShell Window.
# If you chose option to "configure Claude Desktop integration" then restart Claude Desktop
```

The PowerShell script will:

- ✅ Check for and auto-install uv (via winget or PowerShell script)
- ✅ Install dependencies and create executable
- ✅ Prompt for USPTO API key (required) or Detect if you had installed the developer's other USPTO MCPs and ask if want to use existing keys from those installation.
- 🔒 **If entering in API keys, the script will automatically store API keys securely using Windows DPAPI encryption**
- ✅ Ask if you want Claude Desktop integration configured
- 🔒 **Offer secure configuration method (recommended) or traditional method (API keys in plain text in the MCP JSON file)**
- ✅ Backups and then automatically merge with existing Claude Desktop config (preserves other MCP servers)
- ✅ Provide installation summary and next steps

### Claude Desktop Configuration - Manual installs

```json
{
  "mcpServers": {
    "uspto_enriched_citations": {
      "command": "uv",
      "args": ["--directory", "C:/Users/YOUR_USERNAME/uspto_enriched_citation_mcp",
               "run",
               "uspto_enriched_citation_mcp"
      ],
      "env": {
        "USPTO_API_KEY": "your_actual_api_key_here"
      }
    }
  }
}
```

**For detailed installation, manual setup, and troubleshooting**, see **[INSTALL.md](./INSTALL.md)**

## 🔑 Key Benefits

- **🗺️Smart Field Mapping & Selection** - User-configurable field sets via YAML without code changes
- **📊Progressive Disclosure Workflow** - Minimal discovery → Balanced analysis → Detailed citation examination
- **🎯Token-Saving Context Reduction** - 90-95% reduction to optimized search results
- **📋Lucene Query Syntax Support** - Full Apache Lucene Query Parser Syntax with validation
- **✨Citation-Specific Features** - Decision types (CITED/DISCARDED/REFERRED/FOLLOWED), citation context, passage analysis
- **🔗Cross-MCP Integration** - Links to Patent File Wrapper, PTAB, and other USPTO MCPs
- **:computer:AI-Powered Data Extraction** - Uses machine learning and NLP data extraction from USPTO
- **:alarm_clock:Time-Coverage** - Office actions mailed from October 1, 2017 to 30 days prior to current date
- **🛡️Production-Ready Resilience** - Structured logging, retry logic, error handling, timeout handling

### Workflow Design - All Performed by LLM with Minimal User Guidance

**User Requests the following:**

- *"Find all citations for application 16751234 and analyze the citation patterns"*
- *"Show me citations from Apple Inc in technology center 2100"*
- *"Research examiner citation patterns for art unit 2854"*
- *"Analyze citation decision types for machine learning patents filed in 2023"*
- *"Find citations that were CITED (not DISCARDED) in software classification 706"*

**LLM Performs these steps:**

**Step 1: Discovery minimal** → **Step 2: Filter & Select** → **Step 3: Analyze (optional)** → **Step 4: Citation Details (optional)** → **Step 5: Cross-MCP Integration (optional)**

The field configuration supports an optimized research progression:

1. **Discovery minimal** returns 50-100 citations efficiently with essential identifiers and decision info
2. **Filter & Select** from results to identify most relevant citations for detailed analysis
3. **Analyze (optional)** detailed research using balanced field set when comprehensive analysis needed
4. **Citation Details (optional)** get complete citation record with optional citing context and passage analysis
5. **Cross-MCP Integration (optional)** connect citations to prosecution history, PTAB challenges, or knowledge base research

## 🎯 Prompt Templates

The Citations MCP provides **5 guided workflow prompts** accessible directly in Claude Desktop UI. These templates automate complex multi-step citation analysis workflows and eliminate the need to memorize tool syntax.

**For detailed prompt documentation, usage examples, and cross-MCP integration patterns, see [PROMPTS.md](PROMPTS.md).**

### Core Prompt Workflows

| Prompt Name | Purpose |
|-------------|---------|
| `patent_citation_analysis` | Complete citation analysis for specific patents with prosecution context |
| `enhanced_examiner_behavior_intelligence_PFW_PTAB_FPD` | Comprehensive examiner profiling with citations, petitions, PTAB correlation |
| `litigation_citation_research_PFW_PTAB` | Complete litigation research package with prosecution & PTAB analysis |
| `technology_citation_landscape_PFW` | Map prior art landscape for technology areas |
| `art_unit_citation_assessment` | Analyze art unit citation norms and examiner patterns |

**Key Features Across All Templates:**

- **Enhanced Input Processing** - Flexible identifier support (patent numbers, application numbers, title keywords)
- **Smart Validation** - Automatic format detection and guidance
- **Cross-MCP Integration** - Seamless workflows with PTAB, FPD, Citations, and Pinecone MCPs

## 📊 Available Functions

### Search Functions (Progressive Disclosure Tools)

| Function (Display Name) | Use Case | Requirements |
|----------|----------|------------------|
| `search_citations_minimal` | Ultra-fast citation discovery with 8 essential fields | USPTO_API_KEY |
| `search_citations_balanced` | Comprehensive citation analysis with 18+ fields for detailed research | USPTO_API_KEY |

**Discovery Search Tier (`search_citations_minimal`)**: Identify relevant citations quickly

- **Essential 8 fields**: Core identifiers (citedReferenceIdentifier, applicationNumberText, patentNumber)
- **Decision intelligence**: Decision types, citing office dates, art unit analysis
- **Cross-reference ready**: Links to Patent File Wrapper and PTAB databases
- **90-95% context reduction**: Focus on most critical information for discovery

**Balanced Search Tier (`search_citations_balanced`)**: Comprehensive citation analysis  

- **18+ key fields**: Technical classifications, examiner information, filing/grant dates
- **Integration ready**: Complete field set for portfolio and competitive intelligence
- **80-85% context reduction**: Rich metadata without unnecessary document bloat

### Analysis Functions

| Function (Display Name) | Purpose | Requirements |
|----------|---------|------------|
| `get_citation_details` | Complete citation details by unique identifier with optional citing context. **⚠️ Returns metadata only - use PFW MCP 2-step workflow for actual documents** | USPTO_API_KEY |
| `get_citation_statistics` | Get database statistics and aggregations for strategic planning | USPTO_API_KEY |
| `get_available_fields` | Discover searchable field names and query syntax guidance | None |
| `validate_query` | Validate Lucene syntax and get optimization suggestions | None |

**Detailed Citation Tier (`get_citation_details`)**: Single citation deep dive

- **Complete record**: All available citation metadata with formatted presentation
- **Optional context**: Include citing application details and passage-level analysis
- **Strategic insights**: Decision reasoning, relevance scores, relationship mapping

### LLM Guidance Function

| Function (Display Name) | Purpose | Requirements |
|----------|---------|------------|
| `citations_get_guidance` | Context-efficient selective guidance sections | None |

#### Context-Efficient Guidance System

**`citations_get_guidance` Tool** - Solves MCP Resources visibility problem with selective guidance sections:

🎯 **Quick Reference Chart** - Know exactly which section to call:

- 🔍 "Find citations by examiner/application/tech" → fields
-  📄 "Understand citation categories (X/Y/NPL)" → citation_codes
-  🔖 "Citation data coverage (2017+)" → data_coverage
-  🤝 "PFW workflow for office action documents" → workflows_pfw
-  🚩 "PTAB citation correlation" → workflows_ptab
-  📊 "FPD petition citation patterns" → workflows_fpd
-  🏢 "Complete lifecycle analysis" → workflows_complete
-  ⚙️ "Tool guidance and parameters" → tools
-  ❌ "Search errors or query issues" → errors
-  💰 "Reduce API costs and optimize" → cost

**Patent Attorney Workflows:**

- **Due Diligence**: Citation risk assessment and portfolio analysis
- **Prior Art Investigation**: Patentability research and invalidity analysis
- **Prosecution Strategy**: Examiner pattern analysis and response tactics
- **Competitive Intelligence**: Technology landscape and market positioning

**Cross-MCP Integration Workflows:**
- **PFW + Citations**: Connect citations to prosecution history for context
- **PTAB + Citations**: Correlate citation outcomes with challenge success rates
- **FPD + Citations**: Petition red flags and prosecution quality assessment
- **Complete Lifecycle Analysis**: PFW → Citations → PTAB → FPD integrated workflows
- **Knowledge Base Research**: Integrate with Pinecone Assistant for MPEP guidance

**Cost Optimization Guidance:**
- Start with minimal discovery to identify key citations
- Progress to balanced analysis only for strategically important citations
- Use ultra-minimal mode with custom fields parameter for 99% token reduction
- Validate complex queries before execution to avoid API waste
- Leverage cross-MCP integration to prevent duplicate research

The tool provides specific workflows, field recommendations, API call optimization strategies, and cross-MCP integration patterns for maximum efficiency. See **[USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)** for detailed examples and integration workflows.

## 🔧 Field Customization

### User-Configurable Field Sets

The MCP server supports user-customizable field sets through YAML configuration at the project root. You can modify field sets that minimal and balanced searches bring back without changing any code!

**Configuration file:** `field_configs.yaml` (in project root)

### Easy Customization Process

1. **Open** `field_configs.yaml` in the project root directory
2. **Uncomment fields** you want by removing the `#` symbol
3. **Save the file** - changes take effect on next Claude Desktop restart
4. **Use the simplified tools** with your custom field selections

### Available Field Sets (Progressive Workflow)

- **`citations_minimal`** - Ultra-minimal for citation discovery: **8 essential fields** for high-volume discovery (50-100 results)
- **`citations_balanced`** - Comprehensive citation analysis: **18 key fields** for detailed citation analysis and portfolio research

### Professional Field Categories Available

**⚠️ API v3 Field Reality (22 total fields as of 2024-07-11)**

- **Core Identifiers**: `citedDocumentIdentifier`, `patentApplicationNumber`, `publicationNumber`, `id`
- **Citation Metadata**: `citationCategoryCode`, `examinerCitedReferenceIndicator`, `applicantCitedExaminerReferenceIndicator`
- **Organizational**: `groupArtUnitNumber`, `techCenter`, `workGroupNumber`
- **Temporal**: `officeActionDate`, `createDateTime`
- **Content**: `passageLocationText`, `relatedClaimNumberText`, `qualitySummaryText`, `officeActionCategory`
- **Reference Details**: `inventorNameText`, `kindCode`, `countryCode`, `nplIndicator`
- **System**: `createUserIdentifier`, `obsoleteDocumentIdentifier`

**❌ Fields NOT Available (despite code references):**
- `examinerNameText`, `firstApplicantName`, `decisionTypeCode`, `decisionTypeCodeDescriptionText`
- `inventionTitle`, `uspcClassification`, `cpcClassificationBag`, `patentStatusCodeDescriptionText`
- For examiner analysis: Use PFW MCP → get application numbers → search citations

### Example Customization

**File: `field_configs.yaml`**
```yaml
predefined_sets:
  citations_minimal:
    description: "Essential fields for citation discovery (90-95% context reduction)"
    fields:
      # === CROSS-MCP INTEGRATION FIELDS ===
      - patentApplicationNumber               # → Patent File Wrapper MCP
      - publicationNumber                     # → PTAB MCP (if granted)
      - groupArtUnitNumber                   # → All USPTO MCPs

      # === CITATION CORE FIELDS ===
      - citedDocumentIdentifier              # Citation reference
      - citationCategoryCode                 # X=US patent, Y=foreign, NPL=non-patent literature
      - techCenter                          # Technology classification
      - officeActionDate                    # Temporal analysis
      - examinerCitedReferenceIndicator      # Examiner vs Applicant
```

## 🔗 Lucene Query Syntax Guide

### Advanced Query Examples

**Field-Specific Searches:**
```sql
patentApplicationNumber:18010777                    # Exact application match
groupArtUnitNumber:1759                               # Art unit search
techCenter:2100                                       # Technology center match
inventorNameText:Smith*                               # Inventor name prefix wildcard
```

**Boolean Logic:**
```sql
techCenter:2100 AND groupArtUnitNumber:2854           # Boolean AND
citationCategoryCode:X OR citationCategoryCode:Y      # Boolean OR (US or foreign patents)
techCenter:2100 NOT groupArtUnitNumber:1600          # Boolean NOT
```

**Range and Wildcard:**
```sql
officeActionDate:[2023-01-01 TO 2023-12-31]         # Date range
patentApplicationNumber:18*                           # Wildcard application search
citedDocumentIdentifier:US*                           # Cited document wildcard
```

**Citation Indicators:**
```sql
examinerCitedReferenceIndicator:true                  # Only examiner-cited references
nplIndicator:true                                     # Non-patent literature only
citationCategoryCode:NPL                              # NPL citations
```

**Complex Multi-Field:**
```sql
(citationCategoryCode:X OR citationCategoryCode:Y) AND techCenter:2100
groupArtUnitNumber:[2000 TO 2999] AND examinerCitedReferenceIndicator:true
officeActionDate:[2023-01-01 TO 2024-12-31] AND nplIndicator:false
```

## 🔗 Cross-MCP Integration

This MCP is designed to work seamlessly with other USPTO MCPs for comprehensive patent lifecycle analysis:

### Related USPTO MCP Servers

| MCP Server | Purpose | GitHub Repository |
|------------|---------|-------------------|
| **USPTO Patent File Wrapper (PFW)** | Prosecution history & documents | [uspto_pfw_mcp](https://github.com/john-walkoe/uspto_pfw_mcp.git) |
| **USPTO Final Petition Decisions (FPD)** | Petition decisions during prosecution | [uspto_fpd_mcp](https://github.com/john-walkoe/uspto_fpd_mcp.git) |
| **USPTO Patent Trial and Appeal Board (PTAB)** | Post-grant challenges | [uspto_ptab_mcp](https://github.com/john-walkoe/uspto_ptab_mcp.git) |
| **Pinecone Assistant MCP** | Patent law knowledge base (MPEP, examination guidance) | [pinecone_assistant_mcp](https://github.com/john-walkoe/pinecone_assistant_mcp.git) |

### Integration Overview

The **USPTO Enriched Citation API v3 MCP** provides AI-powered insight into patent evaluation process, revealing what prior art and references examiners consider when making decisions. When combined with other MCPs, it enables:

- **Citations → PFW**: Understand citation context by cross-referencing with prosecution history
- **Citations → PTAB**: Correlate citation patterns with post-grant challenge outcomes
- **PFW → Citations**: Identify citation red flags during prosecution history review
- **Citations → RAG**: Research MPEP guidance and examination standards before detailed analysis
- **Complete Lifecycle**: PFW + Citations + PTAB + RAG for comprehensive analysis

### ⚠️ Document Retrieval: Citation Metadata vs. Actual Documents

**CRITICAL: The Citation API returns METADATA only, NOT actual documents.**

The Enriched Citation API provides AI-extracted citation data (who cited what, when, in which claims, passage locations) but does NOT provide:
- ❌ Office action PDF documents
- ❌ Cited patent full-text documents
- ❌ Prosecution history documents
- ❌ Any downloadable files

**To get actual documents, use the 2-STEP PFW MCP workflow:**

**Step 1: Get Document List (Always Required)**
```python
# Use selective filtering to avoid context explosion
docs = pfw_get_application_documents(
    app_number='17896175',  # from citation['patentApplicationNumber']
    document_code='CTFR',   # See decoder below
    limit=20
)
```

**Document Code Decoder (Citation-Related Documents):**
- **CTFR**: Non-Final Office Action (where citation appears)
- **CTNF**: Final Office Action Rejection
- **NOA**: Notice of Allowance (citation overcame or not used)
- **892**: Examiner's Search Strategy & Citations List
- **IDS**: Applicant's Information Disclosure Statement

**Step 2a: LLM Analysis (Extract Text for Questions)**
```python
# When user asks: "What did the examiner say about this citation?"
content = pfw_get_document_content(
    app_number='17896175',
    document_identifier=docs['documents'][0]['documentIdentifier']
)
# Analyze extracted text and answer user's question
```

**Step 2b: User Download (Provide PDF Link)**
```python
# When user says: "Get me the office action" or "I want to review it"
download = pfw_get_document_download(
    app_number='17896175',
    document_identifier=docs['documents'][0]['documentIdentifier']
)
# Present as: **📁 [Download Office Action]({download['proxy_download_url']})**
```

**When to Use Each:**
- ✅ **Use `pfw_get_document_content`** when LLM needs to analyze content and answer questions
- ✅ **Use `pfw_get_document_download`** when user explicitly requests document or needs proof
- ❌ **DON'T skip Step 1** - `document_identifier` is always required from `pfw_get_application_documents`

### Key Integration Patterns

**Cross-Referencing Fields:**
- `patentApplicationNumber` - Primary key linking citations to PFW prosecution history
- `publicationNumber` - Patent numbers linking to PTAB post-grant challenges
- `groupArtUnitNumber` - Art unit analysis across all MCPs
- `inventorNameText` - Inventor matching across databases

**⚠️ Examiner Analysis Requires Two-Step Workflow (Ultra-Minimal Mode):**

**Critical: Use wildcard-first strategy with custom fields for 99% token reduction!**

1. **PFW MCP** - Get application numbers with ultra-minimal fields:
   ```python
   # ✅ CORRECT: Use _minimal tool with custom fields parameter
   pfw_apps = pfw_search_applications_minimal(
       query='examinerNameText:SMITH* AND filingDate:[2015-01-01 TO *]',
       fields=['applicationNumberText', 'applicationMetaData.examinerNameText'],
       limit=50
   )
   # Result: ~5KB for 50 apps (vs ~25KB preset minimal, ~500KB full data)
   
   # ❌ WRONG: Don't use convenience parameters (exact match often fails)
   # pfw_apps = pfw_search_applications_minimal(examiner_name='SMITH, JOHN')
   
   # ❌ WRONG: Don't use short field names (causes API errors)
   # fields=['applicationNumber', 'examinerName']  # Missing 'applicationMetaData.' prefix
   ```

2. **Citation MCP** - Search citations by `patentApplicationNumber`:
   ```python
   for app in pfw_apps[:20]:  # Limit to 20 to prevent token explosion
       citations = search_citations_minimal(
           criteria=f'patentApplicationNumber:{app.applicationNumberText}',
           rows=50
       )
   ```

3. Fields like `examinerNameText`, `firstApplicantName`, `decisionTypeCode` are NOT in the Citation API

**Progressive Workflow:**

1. **Citation Discovery** (Citations): Find relevant citation patterns with minimal search
2. **Prosecution Context** (PFW): Cross-reference citing applications with prosecution history using ultra-minimal fields
3. **Challenge Assessment** (PTAB): Check if cited patents faced post-grant challenges
4. **Knowledge Research** (RAG): Research MPEP guidance and examination standards
5. **Strategic Analysis**: Combine insights across multiple data sources for informed decision-making

**Cost Optimization with Cross-MCP (Token Efficiency):**

| Integration Pattern | Old Approach | Ultra-Minimal Approach | Token Savings |
|---------------------|--------------|------------------------|---------------|
| **Examiner Analysis** | Preset minimal (15 fields) | Custom fields (2-3 fields) | 80-87% reduction |
| **50 PFW Apps** | ~25KB | ~5KB | 80% reduction |
| **Art Unit Analysis** | Exact match + 15 fields | Wildcard + 2 fields | 87% + higher hit rate |

**Best Practices:**
- ✅ Use `pfw_search_applications_minimal` WITH custom `fields` parameter
- ✅ Use wildcard-first strategy: `examinerNameText:SMITH*` (not exact match)
- ✅ Use FULL field paths: `applicationMetaData.examinerNameText` (not short names)
- ✅ Filter by date in query: `filingDate:[2015-01-01 TO *]` (citation-eligible apps only)
- ✅ Limit cross-MCP analysis to top 20 results (prevents token explosion)
- Use citations to identify relevant prosecution applications before PFW queries
- Research PTAB outcomes for patents with specific citation patterns
- Validate examination practices against MPEP guidance before expensive document extraction

For detailed integration workflows, cross-referencing examples, and complete use cases, see [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md#cross-mcp-integration-workflows).

## 🛠️ Installation & Setup

### Prerequisites

- **Git installed** or the source files
- **uv Package Manager** - Handles Python installation automatically. If using Quick Start Windows PowerShell install, uv will be installed automatically if not present.
- **USPTO API Key** (required, free from [USPTO Open Data Portal](https://data.uspto.gov/myodp/)) - See **[API Key Guide](API_KEY_GUIDE.md)** for step-by-step instructions with screenshots
- **Claude Desktop** (for MCP integration)

### Installation

See [INSTALL.md](INSTALL.md) for complete cross-platform installation guide.

### Claude Desktop Windows Configuration

**For uv installations, use this config:**

```json
{
  "mcpServers": {
    "uspto_enriched_citation": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/Users/YOUR_USERNAME/uspto_enriched_citation_mcp",
        "run",
        "uspto-enriched-citation-mcp"
      ],
      "env": {
        "USPTO_ECITATION_API_KEY": "your_actual_USPTO_api_key_here",
        "ECITATION_RATE_LIMIT": "100"
      }
    }
  }
}
```

**Important Notes:**

- Replace `YOUR_USERNAME` with your actual username
- Replace `your_actual_USPTO_api_key_here` with your real USPTO API key
- **No .env files needed** - Configuration handled entirely through Claude Desktop environment variables
- Follows the same pattern as other USPTO MCPs (uspto_fpd, uspto_pfw, uspto_ptab)
- For testing scripts, you'll still need the environment variable set
- See [INSTALL.md](INSTALL.md) for additional configuration options

## 📈 Performance Comparison

| Method | Response Size | Context Usage | Features |
|--------|---------------|---------------|----------|
| **Direct curl** | ~50KB+ | High | Raw API access with full Lucene syntax support |
| **MCP Balanced** | ~8KB | Medium | Key fields + classification + cross-reference capability |
| **MCP Minimal** | ~2KB | Very Low | Essential identifiers + decision types only |

## 🧪 Testing

### Core Tests (Essential)

**With uv (Recommended):**
```bash
# Test core functionality
uv run python tests/test_basic.py

# Test with pytest
uv run pytest
```

**With traditional Python:**
```bash
python tests/test_basic.py
pytest
```

### Expected Outputs

**test_basic.py:**
```
✅ ALL TESTS PASSED - USPTO Enriched Citation MCP working correctly!
```

See [tests/README.md](tests/README.md) for comprehensive testing guide.

## 📁 Project Structure

```
uspto_enriched_citation_mcp/
├── field_configs.yaml             # Root-level field customization
├── .gitignore                     # Git ignore patterns
├── src/
│   └── uspto_enriched_citation_mcp/
│       ├── __init__.py            # Package initialization
│       ├── __main__.py           # Entry point for -m execution
│       ├── main.py                 # MCP server with 7 tools
│       ├── config/
│       │   ├── settings.py        # Environment configuration
│       │   └── tool_reflections.py # LLM guidance and metadata
│       └── api/
│           ├── __init__.py         # API package init
│           └── client.py          # USPTO API client
├── deploy/
│   ├── linux_setup.sh            # Linux deployment script
│   └── windows_setup.ps1         # PowerShell deployment script
├── tests/                         # Test files
│   ├── __init__.py             # Test package init
│   └── test_basic.py           # Core functionality tests
├── pyproject.toml                 # Package configuration
├── uv.lock                        # uv lockfile (if using uv)
├── README.md                      # This file
├── INSTALL.md                     # Installation guide
├── USAGE_EXAMPLES.md              # Function examples and workflows
├── SECURITY_GUIDELINES.md         # Security best practices
└── SECURITY_SCANNING.md          # Secret detection and prevention guide
```

## 🔍 Troubleshooting

### Common Issues

#### API Key Issues
- **For Claude Desktop:** API keys in config file are sufficient
- **For test scripts:** Environment variables must be set

**Setting USPTO API Key for Testing:**
- **Windows Command Prompt:** `set USPTO_ECITATION_API_KEY=your_key`
- **Windows PowerShell:** `$env:USPTO_ECITATION_API_KEY="your_key"`
- **Linux/macOS:** `export USPTO_ECITATION_API_KEY=your_key`

#### uv vs pip Issues
- **uv advantages:** Better dependency resolution, faster installs
- **Mixed installation:** Can use both `uv sync` and `pip install -e .`
- **Testing:** Use `uv run` prefix for uv-managed projects

#### Lucene Query Issues
- **Cause:** Invalid Lucene syntax or field names
- **Solution:** Use `validate_query` tool to check syntax and get suggestions
- **Common**: Missing quotes, unbalanced parentheses, wrong field names

#### Fields Not Returning Data
- **Cause:** Field name not in API or configuration
- **Solution:** Use `get_available_fields` to discover correct field names

#### Authentication Errors
- **Cause:** Missing or invalid API key
- **Solution:** Verify `USPTO_ECITATION_API_KEY` environment variable or Claude Desktop config
- **API Key Source:** Get free API key from [USPTO Open Data Portal](https://data.uspto.gov/myodp/)

#### MCP Server Won't Start
- **Cause:** Missing dependencies or incorrect paths
- **Solution:** Re-run setup script, restart Claude Desktop and verify configuration

### Getting Help

1. Check the test scripts for working examples
2. Review the field configuration in `field_configs.yaml`
3. Verify your Claude Desktop configuration matches the provided templates
4. Use `get_tool_reflections` for workflow-specific guidance

## 🛡️ Security & Production Readiness

### Enhanced Error Handling
- **Structured logging** - Request ID tracking for better debugging and monitoring
- **Request timeout handling** - Configurable timeouts for API reliability
- **Production-grade responses** - Clean error messages without internal system details
- **Environment validation** - API key format and presence checking
- **Input sanitization** - Safe handling of user queries and parameters

### Security Features
- **🔒 Secure API Key Storage (Windows DPAPI)** - Encrypted API key storage using Windows Data Protection API
  - Per-user, per-machine encryption (only you on your machine can decrypt)
  - No plain-text API keys in configuration files
  - Automatic fallback to environment variables on non-Windows systems
  - Zero external dependencies (uses Python ctypes)
- **Claude Desktop environment variables** - No .env files, credentials passed securely through Claude Desktop
- **Follows USPTO MCP patterns** - Consistent with uspto_fpd, uspto_pfw, and uspto_ptab MCPs
- **Comprehensive .gitignore** - Prevents accidental credential commits
- **Security guidelines** - Complete documentation for secure development practices
- **Structured error responses** - No sensitive information leakage in error messages
- **API key validation** - Format checking and presence validation

### Request Tracking & Debugging

All API requests include unique request IDs (8-char UUIDs) for correlation:
```
[a1b2c3d4] Starting POST request to enriched_cited_reference_metadata/v3/records
[a1b2c3d4] Request successful on attempt 1
```

### Documentation
- `SECURITY_GUIDELINES.md` - Comprehensive security best practices
- `tests/README.md` - Complete testing guide with API key setup
- Enhanced error messages with request IDs for better support

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License

## ⚠️ Disclaimer

**THIS SOFTWARE IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND.**

**Independent Project Notice**: This is an independent personal project and is not affiliated with, endorsed by, or sponsored by the United States Patent and Trademark Office (USPTO).

The author makes no representations or warranties, express or implied, including but not limited to:

- **Accuracy & AI-Generated Content**: No guarantee of data accuracy, completeness, or fitness for any purpose. Users are specifically cautioned that outputs generated or assisted by Artificial Intelligence (AI) components, including but not limited to text, data, or analyses, may be inaccurate, incomplete, fictionalized, or represent "hallucinations" (confabulations) by the AI model.
- **Availability**: USPTO API and third-party dependencies may cause service interruptions.
- **Legal Compliance**: Users are solely responsible for ensuring their use of this software, and any submissions or actions taken based on its outputs, strictly comply with all applicable laws, regulations, and policies, including but not limited to:
  - The latest [Guidance on Use of Artificial Intelligence-Based Tools in Practice Before the United States Patent and Trademark Office](https://www.federalregister.gov/documents/2024/04/11/2024-07629/guidance-on-use-of-artificial-intelligence-based-tools-in-practice-before-the-united-states-patent) (USPTO Guidance).
  - The USPTO's Duty of Candor and Good Faith (e.g., 37 CFR 1.56, 11.303), which includes a duty to disclose material information and correct errors.
  - The USPTO's signature requirements (e.g., 37 CFR 1.4(d), 2.193(c), 11.18), certifying human review and reasonable inquiry.
  - All rules regarding inventorship (e.g., each claimed invention must have at least one human inventor).
- **Legal Advice**: This tool provides data access and processing only, not legal counsel. All results must be independently verified, critically analyzed, and professionally judged by qualified legal professionals.
- **Commercial Use**: Users must verify USPTO terms for commercial applications.
- **Confidentiality & Data Security**: The author makes no representations regarding the confidentiality or security of any data, including client-sensitive or technical information, input by the user into the software's AI components or transmitted to third-party services. Users are responsible for understanding and accepting the privacy policies, data retention practices, and security measures of any integrated third-party services.
- **Foreign Filing Licenses & Export Controls**: Users are solely responsible for ensuring that the input or processing of any data, particularly technical information, through this software's AI components does not violate U.S. foreign filing license requirements (e.g., 35 U.S.C. 184, 37 CFR Part 5) or export control regulations (e.g., EAR, ITAR). This includes awareness of potential "deemed exports" if foreign persons access such data or if AI servers are located outside the United States.

**LIMITATION OF LIABILITY:** Under no circumstances shall the author be liable for any direct, indirect, incidental, special, or consequential damages arising from use of this software, even if advised of the possibility of such damages.

### USER RESPONSIBILITY: YOU ARE SOLELY RESPONSIBLE FOR THE INTEGRITY AND COMPLIANCE OF ALL FILINGS AND ACTIONS TAKEN BEFORE THE USPTO.

- **Independent Verification**: All outputs, analyses, and content generated or assisted by AI within this software MUST be thoroughly reviewed, independently verified, and corrected by a human prior to any reliance, action, or submission to the USPTO or any other entity. This includes factual assertions, legal contentions, citations, evidentiary support, and technical disclosures.
- **Duty of Candor & Good Faith**: You must adhere to your duty of candor and good faith with the USPTO, including the disclosure of any material information (e.g., regarding inventorship or errors) and promptly correcting any inaccuracies in the record.
- **Signature & Certification**: You must personally sign or insert your signature on any correspondence submitted to the USPTO, certifying your personal review and reasonable inquiry into its contents, as required by 37 CFR 11.18(b). AI tools cannot sign documents, nor can they perform the required human inquiry.
- **Confidential Information**: DO NOT input confidential, proprietary, or client-sensitive information into the AI components of this software without full client consent and a clear understanding of the data handling practices of the underlying AI providers.
- **Export Controls**: Be aware of and comply with all foreign filing license and export control regulations when using this tool with sensitive technical data.
- **Service Compliance**: Ensure compliance with all USPTO (e.g., Terms of Use for USPTO websites, USPTO.gov account policies, restrictions on automated data mining) terms of service.
- **Security**: Maintain secure handling of API credentials and client information.
- **Testing**: Test thoroughly before production use.
- **Professional Judgment**: This tool is a supplement, not a substitute, for your own professional judgment and expertise.

**By using this software, you acknowledge that you have read this disclaimer and agree to use the software at your own risk, accepting full responsibility for all outcomes and compliance with relevant legal and ethical obligations.**

> **Note for Legal Professionals:** While this tool provides access to patent research tools commonly used in legal practice, it is a data retrieval and AI-assisted processing system only. All results require independent verification, critical professional analysis, and cannot substitute for qualified legal counsel or the exercise of your personal professional judgment and duties outlined in the USPTO Guidance on AI Use.

## 🔗 Related Links

- [USPTO Open Data Portal](https://data.uspto.gov/myodp)
- [USPTO Enriched Citation API v3 Documentation](https://developer.uspto.gov/ds-api/#uspto-enriched-citation-api-v3)
- [Apache Lucene Query Parser Syntax](https://lucene.apache.org/core/3_6_2/queryparsersyntax.html)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Claude](https://claude.ai)
- [uv Package Manager](https://github.com/astral-sh/uv)

## 💝 Support This Project

If you find this USPTO Enriched Citation MCP Server useful, please consider supporting the development! This project was developed during my personal time over many hours to provide a comprehensive, production-ready tool for the patent community.

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://paypal.me/walkoe)

Your support helps maintain and improve this open-source tool for everyone in the patent community. Thank you!

## Acknowledgments

- [USPTO](https://www.uspto.gov/) for providing the Enriched Citation API v3 with AI-powered data extraction capabilities
- [Model Context Protocol](https://modelcontextprotocol.io/) for the MCP specification  
- **[Claude Code](https://claude.ai/code)** for exceptional development assistance, architectural guidance, documentation creation, PowerShell automation, test organization, and comprehensive code development throughout this project
- **[Claude Desktop](https://claude.ai)** for additional development support and testing assistance

---

**Questions?** See [INSTALL.md](INSTALL.md) for complete installation guide or review the test scripts for working examples.