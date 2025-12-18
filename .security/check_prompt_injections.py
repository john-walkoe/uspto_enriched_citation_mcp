#!/usr/bin/env python3
"""
Standalone script for checking files for prompt injection patterns.
Can be used with pre-commit hooks or CI/CD pipelines.

Specifically designed for USPTO Enriched Citation MCP to detect:
- Unicode steganography attacks (emoji-based hiding from Repello.ai article)
- Citation-specific injection attempts (citation data extraction, API bypass)
- Standard prompt injection patterns

Usage:
    python check_prompt_injections.py file1.py file2.txt ...
    python check_prompt_injections.py src/ tests/ *.md
    
Exit codes:
    0 - No prompt injections found
    1 - Prompt injections detected
    2 - Error occurred
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

from prompt_injection_detector import PromptInjectionDetector


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
        description="Check files for prompt injection patterns (USPTO Citation MCP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_prompt_injections.py src/**/*.py
  python check_prompt_injections.py README.md config.yml
  python check_prompt_injections.py --verbose src/ tests/
  
Detected attack categories:
- Instruction override ("ignore previous instructions")
- Prompt extraction ("show me your instructions") 
- Persona switching ("you are now a different AI")
- Output format manipulation ("encode in hex")
- Social engineering ("we became friends")
- USPTO FPD specific ("extract all petition numbers")
- Unicode steganography (emoji-based hiding)

Critical: Detects Unicode Variation Selector steganography
from Repello.ai article where malicious prompts are hidden
in invisible characters appended to innocent text like "Hello!".
"""
    )

    parser.add_argument(
        'files',
        nargs='*',
        help='Files and directories to check for prompt injections'
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

    if not args.files:
        print("No files specified. Use --help for usage.", file=sys.stderr)
        return 2

    detector = PromptInjectionDetector()
    total_issues = 0
    total_files_checked = 0
    files_with_issues = []
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
                'SECURITY_SCANNING.md', 'security_examples.py', 'test_security.py',
                'prompt_injection_detector.py', 'check_prompt_injections.py'
            }:
                continue

            total_files_checked += 1
            findings = check_file(file_path, detector)

            if findings:
                files_with_issues.append(str(file_path))
                total_issues += len(findings)
                
                # Check for Unicode steganography specifically
                for _, match in findings:
                    if 'steganography' in match.lower() or 'variation selector' in match.lower():
                        unicode_steganography_detected = True

                if not args.quiet:
                    print(f"\n[!] Prompt injection patterns found in {file_path}:")
                    for line_num, match in findings:
                        if args.verbose:
                            # Safe display of matches (handle Unicode characters)
                            safe_match = match.encode('ascii', 'replace').decode('ascii')
                            print(f"  Line {line_num:4d}: {safe_match}")
                        else:
                            # Truncate long matches for readability and ensure safe display
                            safe_match = match.encode('ascii', 'replace').decode('ascii')
                            display_match = safe_match[:60] + "..." if len(safe_match) > 60 else safe_match
                            print(f"  Line {line_num:4d}: {display_match}")

    # Summary
    if not args.quiet or total_issues > 0:
        print(f"\n{'='*70}")
        print(f"USPTO Citation MCP Security Scan Results:")
        print(f"Files checked: {total_files_checked}")
        print(f"Files with issues: {len(files_with_issues)}")
        print(f"Total issues found: {total_issues}")
        
        if unicode_steganography_detected:
            print(f"\n[CRITICAL] Unicode steganography detected!")
            print("This indicates potential emoji-based prompt injection attacks")
            print("as described in the Repello.ai article. IMMEDIATE REVIEW REQUIRED.")
        
        if total_issues > 0:
            print(f"\n[WARNING] Prompt injection patterns detected!")
            print("These patterns may indicate attempts to:")
            print("- Override system instructions")  
            print("- Extract sensitive prompts")
            print("- Change AI behavior") 
            print("- Bypass security controls")
            print("- Extract USPTO FPD petition data")
            print("- Hide malicious instructions in Unicode characters")
            print("\nReview these findings to ensure they are not malicious.")
            print("For suspected Unicode steganography, use a Unicode analyzer")
            print("to examine invisible characters in the flagged content.")
        else:
            print("[OK] No prompt injection patterns detected.")
            print("System appears secure against known injection techniques.")

    return 1 if total_issues > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
