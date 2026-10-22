"""Audit line ranges cited in markdown TABLE cells.

`tools/verify_doc_refs.py` only understands `` ```s:e:path `` blocks and inline
``path:line`` mentions. Docs also cite ranges in a table cell next to a linked
file, e.g.::

    | 1 | Two buttons are bound | [`app.py`](../app.py) | 439-466 |

Those ranges were never checked. This tool finds them, resolves the file, and
reports ranges that are out of bounds or empty.

Read-only; exits non-zero when a range is stale.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", "uploads"}

# | ... | [label](path) | 123-456 |
ROW_RE = re.compile(
    r"\[[^\]]*\]\((?P<path>[^)\s]+\.(?:py|yaml|yml|md|txt))\)"
    r"[^\n|]*\|[^\n|]*?(?P<start>\d+)\s*[-–]\s*(?P<end>\d+)"
)


def docs() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.md") if not any(part in SKIP for part in p.parts)
    )


def resolve(raw: str, doc: Path) -> Path | None:
    for base in (ROOT, doc.parent, doc.parent.parent):
        candidate = (base / raw).resolve()
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def main() -> int:
    problems = 0
    checked = 0
    for doc in docs():
        text = doc.read_text(encoding="utf-8")
        rel = doc.relative_to(ROOT).as_posix()
        for match in ROW_RE.finditer(text):
            target = resolve(match.group("path"), doc)
            if target is None:
                continue
            start = int(match.group("start"))
            end = int(match.group("end"))
            total = len(target.read_text(encoding="utf-8").splitlines())
            checked += 1
            if start < 1 or end < start or end > total:
                line = text[: match.start()].count("\n") + 1
                print(
                    f"{rel}:{line}: "
                    f"{target.relative_to(ROOT).as_posix()}:{start}-{end} "
                    f"(file has {total} lines)"
                )
                problems += 1

    print(f"\ntable ranges checked: {checked}; stale: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
