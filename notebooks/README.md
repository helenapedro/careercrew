# CareerCrew presentation notebooks

Open these on a big screen during the technical presentation.
Each notebook has clear section explanations, flow diagrams, source-file
pointers, and small offline demo cells (no Gradio / API key required).

## Talk order

| # | Notebook | Topic | Source files |
|---|----------|--------|--------------|
| 0 | [`00_overview.ipynb`](00_overview.ipynb) | System overview | `ARCHITECTURE.md`, `README.md` |
| 1 | [`01_voice_and_transcript.ipynb`](01_voice_and_transcript.ipynb) | Voice + live transcript | `app.py`, `audio.py` |
| 2 | [`02_mock_interview_flow.ipynb`](02_mock_interview_flow.ipynb) | Full interview loop | `interview.py`, `app.py` |
| 3 | [`03_analyze_pipeline.ipynb`](03_analyze_pipeline.ipynb) | Analyze → crew | `pipeline.py`, `crew.py` |
| 4 | [`04_hitl_and_coaches.ipynb`](04_hitl_and_coaches.ipynb) | HITL + coaches | `review.py`, `coach.py` |

## How to present

1. Open the notebook full-screen (or split with the matching `.py`).
2. Walk the markdown sections top to bottom.
3. Optionally run demo cells for a live simulation.

Deeper per-function guides: [`../docs/code-walkthrough/`](../docs/code-walkthrough/INDEX.md).

## Run notes

```bash
cd Project2/careercrew
# optional: jupyter lab notebooks/
```

Demo cells use plain Python (lists/dicts). They do **not** call OpenAI or Gradio.

To regenerate the `.ipynb` files:

```bash
python notebooks/_build_notebooks.py
```
