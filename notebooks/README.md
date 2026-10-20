# CareerCrew presentation notebooks

Open these in Jupyter / VS Code / Cursor during the professor talk.
Each notebook is **self-contained**: short “Say this” scripts, flow diagrams,
pointers to real source files, and small demo cells you can run offline
(no Gradio, no API key required for the demos).

## Talk order

| # | Notebook | When in the talk | Source files |
|---|----------|------------------|--------------|
| 0 | [`00_overview.ipynb`](00_overview.ipynb) | Minutes 0–3 | `ARCHITECTURE.md`, `README.md` |
| 1 | [`01_voice_and_transcript.ipynb`](01_voice_and_transcript.ipynb) | Minutes 18–25 (voice loop) | `app.py`, `audio.py` |
| 2 | [`02_mock_interview_flow.ipynb`](02_mock_interview_flow.ipynb) | Minutes 18–25 (full interview) | `interview.py`, `app.py` |
| 3 | [`03_analyze_pipeline.ipynb`](03_analyze_pipeline.ipynb) | Minutes 3–12 | `pipeline.py`, `crew.py` |
| 4 | [`04_hitl_and_coaches.ipynb`](04_hitl_and_coaches.ipynb) | Minutes 15–18 + 25–30 | `review.py`, `coach.py` |

## How to present

1. Open the notebook **and** the matching `.py` side-by-side.
2. Read the **Say this** markdown cells out loud (they are oral scripts).
3. Run demo cells only if you want a live chalkboard simulation.
4. Deep detail still lives in [`../docs/code-walkthrough/`](../docs/code-walkthrough/INDEX.md).

## Run notes

```bash
cd Project2/careercrew
# optional: jupyter lab notebooks/
```

Demo cells use plain Python (lists/dicts). They do **not** call OpenAI or Gradio.

To regenerate the `.ipynb` files from the builder script:

```bash
python notebooks/_build_notebooks.py
```
