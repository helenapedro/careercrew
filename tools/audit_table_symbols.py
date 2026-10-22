"""Check that a table row's cited line range really contains the symbol it names.

For every markdown table row shaped like

    | n | `symbol` does something | [`file.py`](../file.py) | 123-456 |

find `symbol` in `file.py` via AST and compare its true line span with the
cited one. Reports rows whose range does not cover the named symbol's start.

Read-only; exits non-zero when a row is stale.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", "uploads"}

ROW_RE = re.compile(
    r"^\|(?P<label>[^\n]*?)"
    r"\[[^\]]*\]\((?P<path>[^)\s]+\.py)\)"
    r"[^\n|]*\|[^\n|]*?(?P<start>\d+)\s*[-–]\s*(?P<end>\d+)\s*\|?\s*$",
    re.MULTILINE,
)
# A backticked identifier in the label, optionally before a dot or paren.
LABEL_SYM_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")


def symbols_in(path: Path) -> dict[str, tuple[int, int]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return {}
    found: dict[str, tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.setdefault(node.name, (node.lineno, node.end_lineno or node.lineno))
    return found


def resolve(raw: str, doc: Path) -> Path | None:
    for base in (ROOT, doc.parent, doc.parent.parent):
        candidate = (base / raw).resolve()
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def main() -> int:
    problems = 0
    checked = 0
    for doc in sorted(p for p in ROOT.rglob("*.md") if not any(x in p.parts for x in SKIP)):
        text = doc.read_text(encoding="utf-8")
        rel = doc.relative_to(ROOT).as_posix()
        for row in ROW_RE.finditer(text):
            target = resolve(row.group("path"), doc)
            if target is None or target.suffix != ".py":
                continue
            label = row.group("label")
            names = LABEL_SYM_RE.findall(label)
            if not names:
                continue
            # Only definition-style rows: the symbol is the subject, as in
            # "| 4 | `_render_prep_chat` — the whole turn |". A row like
            # "| 6.11 | Return the `PipelineResult` |" cites the return
            # statement, not the class, so the span check does not apply.
            lead = label.strip().lstrip("| ")
            # Labels look like " 4 | `_render_prep_chat` — the whole turn | "
            # so drop the leading row number and separator first.
            lead = re.sub(r"^[\d.]+\s*\|\s*", "", lead)
            if not lead.startswith("`"):
                continue
            first = names[0]
            if not lead.startswith(f"`{first}`"):
                continue
            names = [first]
            table = symbols_in(target)
            start, end = int(row.group("start")), int(row.group("end"))
            for name in names:
                if name not in table:
                    continue
                real_start, real_end = table[name]
                checked += 1
                # A row may legitimately cite a sub-range (one phase of a
                # function) or a superset (a function plus its helpers).
                inside = start >= real_start and end <= real_end
                covers = start <= real_start and end >= real_end
                if inside or covers:
                    continue
                # Overlap but neither inside nor covering means the window
                # drifts past the symbol: the stale-citation failure mode.
                overlaps = start <= real_end and end >= real_start
                line_no = text[: row.start()].count("\n") + 1
                kind = "drifts past" if overlaps else "does not overlap"
                print(
                    f"{rel}:{line_no}: `{name}` cited {start}-{end} {kind} "
                    f"its real span {real_start}-{real_end} "
                    f"in {target.relative_to(ROOT).as_posix()}"
                )
                problems += 1
    print(f"\nrows with a named symbol checked: {checked}; mismatched: {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
