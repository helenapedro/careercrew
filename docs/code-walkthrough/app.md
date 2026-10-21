# Walkthrough: `app.py` (Gradio UI)

**File purpose:** Builds the Gradio page and wires each button to a callback. It
holds layout and wiring only — no agent logic and no HTML strings.

| Where the work lives | Module |
|----------------------|--------|
| Analyze, Approve, Reject, Request changes | `careercrew/callbacks_analyze.py` |
| Mock interview + both coach chats | `careercrew/callbacks_interview.py` |
| HTML renderers | `careercrew/ui_html.py` |
| Named Analyze outputs | `careercrew/ui_state.py` |
| Worker thread + stage stream | `careercrew/runner.py` |
| Settings, database, review service | `careercrew/services.py` |
| CSS | `careercrew/ui_css.py` |

**Moved in the explainability split.** Do not look for `analyze()` inside this
file. Start at `docs/CODE_TOUR.md` if the line numbers below look stale.

**Flow docs:** [CODE_PATH_ANALYZE](../CODE_PATH_ANALYZE.md) · [HITL](../CODE_PATH_HITL.md) · [MOCK](../CODE_PATH_MOCK_INTERVIEW.md) · [COACH](../CODE_PATH_COACH.md)

---

## Module setup

| Symbol | Role |
|--------|------|
| `_bind_runtime()` | Points `services` and both callback modules at the current settings, store, and review service |
| `_SETTINGS` / `_STORE` / `_REVIEW` | Module-level copies of the same objects; `_bind_runtime()` refreshes them so tests can reload with a temp folder |
| `build_app()` | Layout + `*.click(...)` wiring; returns the `Blocks` object |
| `theme()` / `main()` | Light theme, then `queue().launch()` on `0.0.0.0:_SETTINGS.app_port` |

---

## Layout (open this while talking)

Four tabs, in the order the user works:

| Tab | Controls |
|-----|----------|
| `1 · Analyze match` | Resume input, job input, **Analyze match**, **Clear**, stage tracker, Match report / Interview prep plan sub-tabs, decision dock (Approve / Apply updates / Reject) |
| `2 · Prep coach` | Chatbot + question box |
| `3 · Mock interview` | Start, question slider, audio player, mic or typed answer, live transcript, feedback, overall score |
| `4 · Post-interview coach` | Chatbot + question box |

**Say this:** “`build_app` is layout and wiring only. Every handler lives in a
callback module, so this file reads top to bottom as a page description.”

---

## Wiring (what each control calls)

| Control | Callback | Module |
|---------|----------|--------|
| **Analyze match** | `analyze` (generator) | `callbacks_analyze` |
| **Clear** | inline lambda → `_empty_outputs()` | `app.py` |
| **Try a sample resume / job** | inline lambda → `_read_sample()` | `app.py` |
| **Approve prep bundle** | `approve` | `callbacks_analyze` |
| **Apply updates & re-analyze** | `request_revision` (generator) | `callbacks_analyze` |
| **Reject prep bundle** | `reject` | `callbacks_analyze` |
| **Start interview** | `interview_start` | `callbacks_interview` |
| **Submit answer** | `interview_submit` | `callbacks_interview` |
| Coach send buttons and Enter | `_render_prep_chat` / `_render_post_chat` | `callbacks_interview` |

Analyze outputs are ordered by `careercrew/ui_state.py` `OUTPUT_ORDER`; `app.py`
builds that list once from the `named` dict, so no handler depends on a magic
index.

Both streaming buttons pass `show_progress="hidden"` so Gradio's own progress
chrome does not draw a border around every output on each yield.

---

## How it connects

Calls `callbacks_analyze`, `callbacks_interview`, `ui_html`, `ui_css`,
`ui_state`, `services`, `review`, `session_store`, `config`.
