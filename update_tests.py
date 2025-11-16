#!/usr/bin/env python3
"""Script to update tests from old API to new API."""

import re
from pathlib import Path


def update_test_file(filepath: Path) -> None:
    """Update a single test file."""
    content = filepath.read_text()
    original = content

    # Replace Config(dict) -> Config().update(dict) - but need to handle multiline
    # Simple case: Config({...}) on one line
    content = re.sub(r"Config\(\{([^}]+)\}\)", r"Config().update({\1})", content)

    # Replace Config.load(  ->  Config().update(
    content = content.replace("Config.load(", "Config().update(")

    # Replace Config.from_cli( -> need manual handling, just comment for now
    # This one is more complex, we'll handle separately

    if content != original:
        filepath.write_text(content)
        print(f"Updated {filepath}")
    else:
        print(f"No changes needed for {filepath}")


def main():
    test_dir = Path("tests")
    for test_file in test_dir.glob("test_*.py"):
        print(f"\nProcessing {test_file}")
        update_test_file(test_file)


if __name__ == "__main__":
    main()
