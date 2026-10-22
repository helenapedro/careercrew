# Walkthrough: `main.py` (CLI)

**File purpose:** Non-UI entrypoint for the same `run_analysis` pipeline. Useful for demos/scripts without Gradio. No mock interview or coach UI here.

---

## `_build_parser()`

Defines flags: `--resume`, `--resume-text`, `--jd`, `--jd-file`, `--seniority`.

---

## `main()`

**What:**

1. `load_dotenv()`  
2. Parse args; exit if missing resume or JD source  
3. Ensure `uploads/` exists  
4. If `--resume`: `check_upload` → copy into uploads → store **basename** only  
5. If `--jd-file`: same for JD; else treat `--jd` as text (or read if it is a .txt path) + `redact_pii`  
6. Build `AnalysisRequest` with `make_package_id`  
7. `run_analysis(request)`  
8. Print package JSON + prep plan JSON + warnings  

**Why copy to uploads:** Same confinement rules as the web UI / MCP tools.  
**I/O:** Disk copy, then full pipeline (MCP/LLM).  

---

## How it connects

Same orchestrator as Analyze: [pipeline.md](pipeline.md).
