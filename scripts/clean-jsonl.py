#!/usr/bin/env python3
"""
Clean JSONL files by removing malformed entries.
"""

import json
import sys
from pathlib import Path


def clean_jsonl(filepath: Path) -> tuple[int, int]:
    """Clean a JSONL file, removing malformed entries."""
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return 0, 0

    lines = filepath.read_text().split('\n')
    valid_lines = []
    invalid_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            valid_lines.append(line)
        except json.JSONDecodeError:
            invalid_count += 1
            print(f"  Removing: {line[:60]}...")

    # Write back clean file
    filepath.write_text('\n'.join(valid_lines) + '\n')

    return len(valid_lines), invalid_count


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
    else:
        filepath = Path.home() / ".claude/data/command-usage.jsonl"

    print(f"Cleaning {filepath}")
    valid, invalid = clean_jsonl(filepath)
    print(f"✅ Kept {valid} valid entries, removed {invalid} malformed entries")
