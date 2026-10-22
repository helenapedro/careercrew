"""Check that every code citation in the walkthrough points at real lines.

What it does: parses ``startLine:endLine:path`` code blocks and ``path:line``
mentions in a markdown file and verifies each one against the working tree.
Who calls it: developers and CI, before shipping documentation changes.
What you get: a pass/fail report, or one line per stale citation.

Usage::

    python tools/verify_doc_refs.py
    python tools/verify_doc_refs.py docs/ANALYZE_BUTTON_WALKTHROUGH.md
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: A quoted code block, either ```startLine:endLine:path or ```12:34:path
CODE_BLOCK_RE = re.compile(r"^```[ \t]*(?:startLine:)?(\d+):(\d+):(\S+?)[ \t]*$", re.MULTILINE)

#: `relative/path.py:12` or `relative/path.py:12-34` or `path.py:12,34`
INLINE_REF_RE = re.compile(
    r"(?P<path>(?:[\w.\-]+/)*[\w.\-]+\.(?:py|yaml|yml|md|txt|toml|cfg|ini))"
    r":(?P<lines>\d+(?:\s*[-,]\s*\d+)*)"
)

#: Lines inside a quoted block that use the doc's own truncation marker.
ELLIPSIS_RE = re.compile(r"^\s*(?:\.\.\.|…)\s*$")


@dataclass
class Problem:
    where: int
    message: str

    def __str__(self) -> str:
        return f"line {self.where}: {self.message}"


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _resolve(raw: str, doc: Path) -> Path | None:
    """Resolve a citation path against the repo, then by unique basename.

    Docs cite both full paths (``careercrew/pipeline.py``) and short ones
    (``pipeline.py``). Short names are accepted only when exactly one file in
    the repo matches, so an ambiguous citation cannot silently pass.
    """
    for base in _bases(doc):
        candidate = (base / raw).resolve()
        if candidate.exists():
            return candidate
    return _by_basename(Path(raw).name)


@lru_cache(maxsize=1)
def _basename_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache"}:
            continue
        index.setdefault(path.name, []).append(path)
    return index


def _by_basename(name: str) -> Path | None:
    matches = _basename_index().get(name) or []
    return matches[0] if len(matches) == 1 else None


def _bases(doc: Path) -> list[Path]:
    """Candidate roots for relative citation paths, most specific first."""
    roots = [REPO_ROOT, doc.parent.parent, doc.parent]
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _check_block(match: re.Match, doc_lines: list[str], doc: Path, problems: list[Problem]) -> None:
    start = int(match.group(1))
    end = int(match.group(2))
    raw_path = match.group(3)
    where = doc_lines.index(match.group(0)) + 1 if match.group(0) in doc_lines else 0
    resolved = _resolve(raw_path, doc)
    if resolved is None:
        problems.append(Problem(where, f"code block cites a missing file: {raw_path}"))
        return
    source = resolved.read_text(encoding="utf-8").splitlines()
    total = len(source)
    if start < 1 or end < start:
        problems.append(Problem(where, f"invalid range {start}:{end} for {_rel(resolved)}"))
        return
    if end > total:
        problems.append(
            Problem(
                where,
                f"range {start}:{end} exceeds {_rel(resolved)} ({total} lines)",
            )
        )
        return

    quoted = _quoted_body(match)
    if quoted is None:
        return
    problems.extend(
        Problem(where, message)
        for message in _compare(quoted, source[start - 1 : end], _rel(resolved), start)
    )


def _quoted_body(match: re.Match) -> list[str] | None:
    """Lines between this fence and the closing fence, or None when absent."""
    rest = match.string[match.end() :]
    lines = rest.splitlines()
    if not lines:
        return None
    body: list[str] = []
    for line in lines[1:]:  # skip the remainder of the fence line itself
        if line.strip().startswith("```"):
            return body
        body.append(line)
    return None


def _compare(quoted: list[str], actual: list[str], rel: str, start: int) -> list[str]:
    """Compare a quoted block against the real lines, tolerating the doc's markers."""
    problems: list[str] = []
    # Drop a single leading/trailing blank line (formatting, not content).
    while quoted and not quoted[0].strip():
        quoted = quoted[1:]
    while quoted and not quoted[-1].strip():
        quoted = quoted[:-1]

    # Quoted blocks may elide lines with a bare "..." marker.
    actual_cursor = 0
    for offset, line in enumerate(quoted):
        if ELLIPSIS_RE.match(line):
            actual_cursor = min(actual_cursor + 1, len(actual))
            continue
        if actual_cursor >= len(actual):
            problems.append(f"{rel}:{start + offset} quoted line has no matching source line")
            return problems
        if line.rstrip() != actual[actual_cursor].rstrip():
            problems.append(
                f"{rel}:{start + actual_cursor} content mismatch "
                f"(quoted: {line.strip()[:60]!r} | actual: {actual[actual_cursor].strip()[:60]!r})"
            )
            return problems
        actual_cursor += 1
    return problems


def _check_inline(
    match: re.Match, doc_lines: list[str], doc: Path, problems: list[Problem]
) -> None:
    raw_path = match.group("path")
    resolved = _resolve(raw_path, doc)
    if resolved is None:
        return  # prose may name non-repo files; block citations are authoritative
    total = _line_count(resolved)
    where = _line_of(doc_lines, match.group(0))
    for token in re.split(r"\s*,\s*", match.group("lines")):
        if "-" in token:
            first, _, last = token.partition("-")
            low, high = int(first), int(last)
        else:
            low = high = int(token)
        if low < 1 or high < low or high > total:
            problems.append(
                Problem(
                    where,
                    f"{_rel(resolved)}:{low}-{high} is out of range (file has {total} lines)",
                )
            )


def _line_of(doc_lines: list[str], needle: str) -> int:
    for index, line in enumerate(doc_lines, start=1):
        if needle in line:
            return index
    return 0


def verify(doc: Path) -> list[Problem]:
    """Return every stale citation found in ``doc``."""
    text = doc.read_text(encoding="utf-8")
    doc_lines = text.splitlines()
    problems: list[Problem] = []

    for match in CODE_BLOCK_RE.finditer(text):
        _check_block(match, doc_lines, doc, problems)

    for match in INLINE_REF_RE.finditer(text):
        _check_inline(match, doc_lines, doc, problems)

    return problems


def main(argv: list[str]) -> int:
    docs = (
        [Path(arg).resolve() for arg in argv[1:]]
        if len(argv) > 1
        else [REPO_ROOT / "docs" / "ANALYZE_BUTTON_WALKTHROUGH.md"]
    )
    failures = 0
    for doc in docs:
        if not doc.exists():
            print(f"MISSING  {doc}")
            failures += 1
            continue
        problems = verify(doc)
        checkable = len(CODE_BLOCK_RE.findall(doc.read_text(encoding="utf-8")))
        if problems:
            failures += len(problems)
            print(f"FAIL     {_rel(doc)} ({len(problems)} problem(s))")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"OK       {_rel(doc)} ({checkable} code citation(s) verified)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
