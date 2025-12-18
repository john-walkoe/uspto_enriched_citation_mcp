#!/usr/bin/env python3
"""
Standalone script for checking files for prompt injection patterns.
Can be used with pre-commit hooks or CI/CD pipelines.

Usage:
    python check_prompt_injections.py file1.py file2.txt ...
    
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
            
        # Only check text-based files
        text_extensions = {'.py', '.txt', '.md', '.yml', '.yaml', '.json', '.js', '.ts', '.html', '.xml', '.csv'}
        if filepath.suffix.lower() not in text_extensions and filepath.suffix:
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
        description="Check files for prompt injection patterns",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_prompt_injections.py src/**/*.py
  python check_prompt_injections.py README.md config.yml
  
Common prompt injection patterns detected:
- Instruction override attempts ("ignore previous instructions")
- Prompt extraction ("show me your instructions") 
- Persona switching ("you are now a different AI")
- Output format manipulation ("encode in hex")
- Social engineering ("we became friends")
"""
    )
    
    parser.add_argument(
        'files',
        nargs='*', 
        help='Files to check for prompt injections'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )
    
    parser.add_argument(
        '--quiet', '-q', 
        action='store_true',
        help='Only show summary'
    )
    
    args = parser.parse_args()
    
    if not args.files:
        print("No files specified. Use --help for usage.", file=sys.stderr)
        return 2
    
    detector = PromptInjectionDetector()
    total_issues = 0
    total_files_checked = 0
    files_with_issues = []
    
    for file_pattern in args.files:
        filepath = Path(file_pattern)
        
        if filepath.is_file():
            files_to_check = [filepath]
        else:
            # Handle glob patterns
            files_to_check = list(filepath.parent.glob(filepath.name)) if filepath.parent.exists() else []
        
        for file_path in files_to_check:
            if not file_path.is_file():
                continue
                
            total_files_checked += 1
            findings = check_file(file_path, detector)
            
            if findings:
                files_with_issues.append(str(file_path))
                total_issues += len(findings)
                
                if not args.quiet:
                    print(f"\n[!] Prompt injection patterns found in {file_path}:")
                    for line_num, match in findings:
                        if args.verbose:
                            print(f"  Line {line_num:4d}: {match}")
                        else:
                            # Truncate long matches
                            display_match = match[:60] + "..." if len(match) > 60 else match
                            print(f"  Line {line_num:4d}: {display_match}")
    
    # Summary
    if not args.quiet or total_issues > 0:
        print(f"\n{'='*60}")
        print(f"Files checked: {total_files_checked}")
        print(f"Files with issues: {len(files_with_issues)}")
        print(f"Total issues found: {total_issues}")
        
        if total_issues > 0:
            print(f"\n[WARNING] Prompt injection patterns detected!")
            print("These patterns may indicate attempts to:")
            print("- Override system instructions")  
            print("- Extract sensitive prompts")
            print("- Change AI behavior") 
            print("- Bypass security controls")
            print("\nReview these findings to ensure they are not malicious.")
        else:
            print("[OK] No prompt injection patterns detected.")
    
    return 1 if total_issues > 0 else 0


if __name__ == '__main__':
    sys.exit(main())