"""Check every relative markdown link in the repo resolves.

Read-only; exits non-zero when a link target is missing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".dc",
    "uploads",
}

LINK_RE = re.compile(r"\[[^\]]*\]\((?P<target>[^)\s]+)\)")


def main() -> int:
    problems = 0
    checked = 0
    for doc in sorted(p for p in ROOT.rglob("*.md") if not any(x in p.parts for x in SKIP)):
        text = doc.read_text(encoding="utf-8")
        rel = doc.relative_to(ROOT).as_posix()
        for match in LINK_RE.finditer(text):
            target = match.group("target")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            anchorless = target.split("#", 1)[0]
            if not anchorless:
                continue
            checked += 1
            resolved = (doc.parent / anchorless).resolve()
            if not resolved.exists():
                line = text[: match.start()].count("\n") + 1
                print(f"{rel}:{line}: broken link -> {target}")
                problems += 1
    print(f"\nrelative links checked: {checked}; broken: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
