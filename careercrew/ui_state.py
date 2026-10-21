"""Named outputs for the Analyze and Request-changes callbacks.

What it does: holds the 14 Gradio outputs as fields instead of a magic-index tuple.
Who calls it: callbacks_analyze.py (analyze, request_revision) and the app.py wiring.
What it returns: AnalyzeOutputs, plus as_tuple() for Gradio's ordered output list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gradio as gr

#: The only place output order is defined. Gradio needs a list; names stay here.
OUTPUT_ORDER = (
    "error",
    "status",
    "stages",
    "match_report",
    "prep_plan",
    "approve",
    "reject",
    "revise",
    "package",
    "notes",
    "context",
    "review_guide",
    "run_button",
    "clear_button",
)


def _button(interactive: bool):
    return gr.update(interactive=interactive)


@dataclass
class AnalyzeOutputs:
    """One full update of the Analyze result area."""

    error: str = ""
    status: str = ""
    stages: str = ""
    match_report: str = ""
    prep_plan: str = ""
    approve: object = field(default_factory=lambda: _button(False))
    reject: object = field(default_factory=lambda: _button(False))
    revise: object = field(default_factory=lambda: _button(False))
    package: dict | None = None
    notes: object = field(default_factory=lambda: gr.update(value="", interactive=False))
    context: str | None = None
    review_guide: str = ""
    run_button: object = field(default_factory=lambda: _button(True))
    clear_button: object = field(default_factory=lambda: _button(True))

    def as_dict(self) -> dict:
        """Field name -> value, in OUTPUT_ORDER."""
        return {name: getattr(self, name) for name in OUTPUT_ORDER}

    def as_tuple(self) -> tuple:
        """The ordered list Gradio expects. Call this only at the yield edge."""
        values = self.as_dict()
        return tuple(values[name] for name in OUTPUT_ORDER)

    def apply(self, **changes) -> tuple:
        """Set named fields and return the Gradio tuple."""
        unknown = set(changes) - set(OUTPUT_ORDER)
        if unknown:
            raise KeyError(f"unknown Analyze output(s): {sorted(unknown)}")
        for name, value in changes.items():
            setattr(self, name, value)
        return self.as_tuple()
