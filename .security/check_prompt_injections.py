#!/usr/bin/env python3
"""
Standalone script for checking files for prompt injection patterns.
Can be used with pre-commit hooks or CI/CD pipelines.

Specifically designed for USPTO Enriched Citation MCP to detect:
- Unicode steganography attacks (emoji-based hiding from Repello.ai article)
- Citation-specific injection attempts (citation data extraction, API bypass)
- Standard prompt injection patterns

## Baseline System

This scanner uses a **baseline system** to track known findings and only flag
**NEW** patterns that are not in the baseline. This solves the problem of false
positives from legitimate code and documentation while maintaining protection
against malicious prompt injection attacks.

### How It Works

1. **Baseline File**: `.prompt_injections.baseline` stores known findings
2. **Fingerprinting**: Each finding gets a unique SHA256 hash fingerprint
3. **Comparison**: Scanner checks if each finding is in the baseline
4. **Exit Codes**:
   - `0` - No NEW findings (all findings in baseline)
   - `1` - NEW findings detected (not in baseline)
   - `2` - Error occurred

Usage:
    python check_prompt_injections.py file1.py file2.txt ...
    python check_prompt_injections.py src/ tests/ *.md

Baseline Management:
    python check_prompt_injections.py --update-baseline src/ tests/  # Add new findings to baseline
    python check_prompt_injections.py --force-baseline src/ tests/   # Create new baseline (overwrite)
    python check_prompt_injections.py --baseline src/ tests/         # Check against baseline (CI/CD)

Exit codes:
    0 - No NEW prompt injections found (all findings in baseline)
    1 - NEW prompt injections detected (not in baseline)
    2 - Error occurred
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from prompt_injection_detector import PromptInjectionDetector

# Baseline file name
BASELINE_FILE = '.prompt_injections.baseline'


def generate_fingerprint(filepath: str, line: int, match: str) -> str:
    """
    Generate a unique SHA256 fingerprint for a finding.

    The fingerprint includes the file path, line number, and match content
    to ensure uniqueness even across different files or locations.

    Args:
        filepath: Path to the file where the finding was found
        line: Line number where the finding was found
        match: The actual matched text

    Returns:
        SHA256 hash as a hexadecimal string
    """
    fingerprint_data = f"{filepath}:{line}:{match}"
    return hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()


def load_baseline(baseline_path: Path) -> Dict:
    """
    Load the baseline file.

    Args:
        baseline_path: Path to the baseline file

    Returns:
        Dictionary containing the baseline data (empty if file doesn't exist)
    """
    if baseline_path.exists():
        try:
            with open(baseline_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Failed to load baseline file: {e}", file=sys.stderr)
            return {}
    return {}


def save_baseline(baseline_path: Path, baseline_data: Dict) -> bool:
    """
    Save the baseline data to file.

    Args:
        baseline_path: Path to the baseline file
        baseline_data: Dictionary containing baseline data

    Returns:
        True if save was successful, False otherwise
    """
    try:
        with open(baseline_path, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, indent=2, sort_keys=True)
        return True
    except IOError as e:
        print(f"[ERROR] Failed to save baseline file: {e}", file=sys.stderr)
        return False


def add_finding_to_baseline(baseline_data: Dict, filepath: str, line: int, match: str) -> None:
    """
    Add a finding to the baseline data structure.

    Args:
        baseline_data: Dictionary containing baseline data
        filepath: Path to the file where the finding was found
        line: Line number where the finding was found
        match: The actual matched text
    """
    fingerprint = generate_fingerprint(filepath, line, match)

    # Normalize file path for consistent storage
    if filepath.startswith('./'):
        filepath = filepath[2:]

    # Create file entry if it doesn't exist
    if filepath not in baseline_data:
        baseline_data[filepath] = {}

    # Add the finding to the file's baseline
    baseline_data[filepath][fingerprint] = {
        'line': line,
        'match': match[:100] + '...' if len(match) > 100 else match  # Truncate long matches
    }


def check_file(filepath: Path, detector: PromptInjectionDetector) -> List[Tuple[int, str]]:
    """
    Check a single file for prompt injection patterns.

    Returns:
        List of (line_number, match) tuples
    """
    try:
        # Skip binary files
        if not filepath.is_file():
            return []

        # Only check text-based files (including FPD-specific file types)
        text_extensions = {
            '.py', '.txt', '.md', '.yml', '.yaml', '.json', '.js', '.ts', 
            '.html', '.xml', '.csv', '.rst', '.cfg', '.ini', '.toml',
            '.log', '.env', '.sh', '.bat', '.ps1'
        }
        if filepath.suffix.lower() not in text_extensions and filepath.suffix:
            return []
            
        # Skip files that are likely to contain legitimate security examples or documentation
        excluded_files = {
            # Security documentation and tools
            'SECURITY_SCANNING.md', 'SECURITY_GUIDELINES.md', 'security_examples.py', 'test_security.py',
            'prompt_injection_detector.py', 'check_prompt_injections.py',
            # Documentation files likely to contain examples
            'README.md', 'PROMPTS.md', 'CLAUDE.md',
            # Deployment and configuration scripts
            'linux_setup.sh', 'windows_setup.ps1', 'manage_api_keys.ps1',
        }
        if filepath.name in excluded_files:
            return []
            
        # Skip prompt template files (legitimate use of prompt-related keywords)
        if 'prompt' in filepath.name.lower() and filepath.suffix == '.py':
            return []

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Analyze content
        findings = []
        lines = content.split('\n')

        for line_number, line in enumerate(lines, 1):
            matches = list(detector.analyze_line(line, line_number, str(filepath)))
            for match in matches:
                findings.append((line_number, match))

        return findings

    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return []


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check files for prompt injection patterns (USPTO Enriched Citation MCP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time: Create baseline (will NOT fail if findings exist)
  python check_prompt_injections.py --update-baseline src/ tests/ *.md *.yml *.yaml *.json *.py

  # Normal CI/CD run: Check against baseline (only NEW findings fail)
  python check_prompt_injections.py --baseline src/ tests/ *.yml *.yaml *.json *.py

  # Update baseline to add new legitimate findings
  python check_prompt_injections.py --update-baseline src/ tests/ *.md *.yml *.yaml *.json *.py

  # Force new baseline (overwrite existing)
  python check_prompt_injections.py --force-baseline src/ tests/ *.md *.yml *.yaml *.json *.py

Detected attack categories:
- Instruction override ("ignore previous instructions")
- Prompt extraction ("show me your instructions")
- Persona switching ("you are now a different AI")
- Output format manipulation ("encode in hex")
- Social engineering ("we became friends")
- USPTO Enriched Citation specific ("extract all citation numbers")
- Unicode steganography (emoji-based hiding)

Critical: Detects Unicode Variation Selector steganography
from Repello.ai article where malicious prompts are hidden
in invisible characters appended to innocent text like "Hello!".

Baseline System:
  --baseline:        Use existing baseline (only NEW findings fail)
  --update-baseline: Add new findings to baseline
  --force-baseline:  Create new baseline (overwrite existing)

Exit codes:
  0 - No NEW findings (all findings in baseline)
  1 - NEW findings detected (not in baseline)
  2 - Error occurred
"""
    )

    parser.add_argument(
        'files',
        nargs='*',
        help='Files and directories to check for prompt injections'
    )

    parser.add_argument(
        '--baseline',
        action='store_true',
        help='Use existing baseline (only NEW findings cause failure)'
    )

    parser.add_argument(
        '--update-baseline',
        action='store_true',
        help='Add new findings to baseline'
    )

    parser.add_argument(
        '--force-baseline',
        action='store_true',
        help='Create new baseline (overwrite existing)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output including full matches'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Only show summary (suppress individual findings)'
    )

    parser.add_argument(
        '--include-security-files',
        action='store_true',
        help='Check security documentation files (normally excluded)'
    )

    args = parser.parse_args()

    # Validate baseline options (mutually exclusive)
    baseline_options = [args.baseline, args.update_baseline, args.force_baseline]
    if sum(baseline_options) > 1:
        print("[ERROR] Only one of --baseline, --update-baseline, or --force-baseline can be specified.",
              file=sys.stderr)
        return 2

    if not args.files:
        print("[ERROR] No files specified. Use --help for usage.", file=sys.stderr)
        return 2

    # Initialize baseline
    baseline_path = Path(BASELINE_FILE)
    baseline_data = {}

    if args.baseline or args.update_baseline:
        # Load existing baseline
        baseline_data = load_baseline(baseline_path)
    elif args.force_baseline:
        # Start with empty baseline
        baseline_data = {}

    detector = PromptInjectionDetector()
    total_issues = 0
    total_findings = 0
    total_baseline_findings = 0
    total_new_findings = 0
    total_files_checked = 0
    files_with_issues = []
    files_with_new_issues = []
    unicode_steganography_detected = False

    for file_pattern in args.files:
        filepath = Path(file_pattern)

        if filepath.is_file():
            files_to_check = [filepath]
        elif filepath.is_dir():
            # Recursively check directory
            files_to_check = []
            for ext in ['.py', '.txt', '.md', '.yml', '.yaml', '.json', '.js', '.ts', '.html', '.xml', '.csv']:
                files_to_check.extend(filepath.rglob(f"*{ext}"))
        else:
            # Handle glob patterns
            files_to_check = list(filepath.parent.glob(filepath.name)) if filepath.parent.exists() else []

        for file_path in files_to_check:
            if not file_path.is_file():
                continue

            # Skip security files unless explicitly requested
            if not args.include_security_files and file_path.name in {
                'SECURITY_SCANNING.md', 'SECURITY_GUIDELINES.md', 'security_examples.py', 'test_security.py',
                'prompt_injection_detector.py', 'check_prompt_injections.py', 'PROMPT_INJECTION_BASELINE_SYSTEM.md'
            }:
                continue

            total_files_checked += 1
            findings = check_file(file_path, detector)

            if findings:
                total_issues += len(findings)
                files_with_issues.append(str(file_path))

                # Check for Unicode steganography specifically
                for _, match in findings:
                    if 'steganography' in match.lower() or 'variation selector' in match.lower():
                        unicode_steganography_detected = True

                # Process each finding against baseline
                for line_num, match in findings:
                    total_findings += 1
                    fingerprint = generate_fingerprint(str(file_path), line_num, match)

                    # Normalize file path for baseline lookup
                    norm_path = str(file_path)
                    if norm_path.startswith('./'):
                        norm_path = norm_path[2:]

                    # Check if in baseline
                    in_baseline = False
                    if baseline_data and norm_path in baseline_data:
                        if fingerprint in baseline_data[norm_path]:
                            in_baseline = True
                            total_baseline_findings += 1
                        elif args.update_baseline:
                            # Add to baseline if updating
                            add_finding_to_baseline(baseline_data, norm_path, line_num, match)

                    if not in_baseline:
                        total_new_findings += 1
                        if args.update_baseline:
                            # Add to baseline when updating
                            add_finding_to_baseline(baseline_data, norm_path, line_num, match)
                        elif args.baseline:
                            # Only track new files when checking against baseline
                            if str(file_path) not in files_with_new_issues:
                                files_with_new_issues.append(str(file_path))

                if not args.quiet:
                    print(f"\n[!] Prompt injection patterns found in {file_path}:")
                    for line_num, match in findings:
                        if args.verbose:
                            # Safe display of matches (handle Unicode characters)
                            safe_match = match.encode('ascii', 'replace').decode('ascii')
                            print(f"  Line {line_num:4d}: {safe_match}", end='')
                        else:
                            # Truncate long matches for readability and ensure safe display
                            safe_match = match.encode('ascii', 'replace').decode('ascii')
                            display_match = safe_match[:60] + "..." if len(safe_match) > 60 else safe_match
                            print(f"  Line {line_num:4d}: {display_match}", end='')

                        # Check if in baseline and append tag
                        norm_path = str(file_path)
                        if norm_path.startswith('./'):
                            norm_path = norm_path[2:]

                        fingerprint = generate_fingerprint(norm_path, line_num, match)
                        if baseline_data and norm_path in baseline_data and fingerprint in baseline_data[norm_path]:
                            print(" [BASELINE]", file=sys.stderr)
                        else:
                            print(" [NEW]", file=sys.stderr)

    # Save baseline if updating or forcing
    if args.update_baseline or args.force_baseline:
        if save_baseline(baseline_path, baseline_data):
            # Count total findings in baseline
            total_baseline_entries = sum(len(files) for files in baseline_data.values())
            if not args.quiet:
                print(f"\nBaseline updated: {BASELINE_FILE}")
                print(f"Total tracked findings: {total_baseline_entries}")

    # Summary
    if not args.quiet or total_issues > 0:
        print(f"\n{'='*70}")
        print("USPTO Enriched Citation MCP Security Scan Results:")
        print(f"Files checked: {total_files_checked}")
        print(f"Total findings: {total_findings}")
        print(f"Baseline findings: {total_baseline_findings}")
        print(f"NEW findings: {total_new_findings}  <- Only NEW findings cause failure")
        print(f"Files with findings: {len(files_with_issues)}")
        print(f"Files with NEW findings: {len(files_with_new_issues)}")

        if unicode_steganography_detected:
            print("\n[CRITICAL] Unicode steganography detected!")
            print("This indicates potential emoji-based prompt injection attacks")
            print("as described in the Repello.ai article. IMMEDIATE REVIEW REQUIRED.")

        if total_new_findings == 0:
            print("\n[OK] No NEW prompt injection patterns detected.")
            print("All findings match baseline (existing known findings).")
            return 0
        else:
            print("\n[WARNING] NEW prompt injection patterns detected!")
            print("These patterns may indicate attempts to:")
            print("- Override system instructions")
            print("- Extract sensitive prompts")
            print("- Change AI behavior")
            print("- Bypass security controls")
            print("- Extract USPTO citation data")
            print("- Hide malicious instructions in Unicode characters")
            print("\nReview these findings to ensure they are not malicious.")
            if args.baseline:
                print("\nIf these are legitimate findings, run:")
                print(f"  python check_prompt_injections.py --update-baseline {' '.join(args.files)}")
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
