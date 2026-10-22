# What happens when you press **Analyze match**

A line-by-line trace of one click. Every line number below was verified against
the working tree on 2026-10-21.

**Audience:** explaining the codebase out loud. Read top to bottom; each step
names the file, the line, and *why* the code does it that way.

---

## 0. The one-paragraph answer

You press the button → Gradio calls one Python generator named `analyze` →
it copies your files into `uploads/`, validates them, then hands a request to a
worker thread that runs the five-agent CrewAI crew. While that runs, the
generator keeps yielding progress so the stepper animates. When the crew
finishes, the result is parsed into typed models, checked by guardrails, saved
as `PENDING_REVIEW` in SQLite, and rendered as HTML. The generator ends by
handing you the final tuple of UI updates.

The whole thing is **one generator function**: `analyze` in
`careercrew/callbacks_analyze.py:135`.

---

## 0a. Where the resume and job description go, and how agents pass results

Read this section first if the question is "which agent gets the resume, and
how does agent 1's result reach the next agent?"

**Agent 2 does not receive agent 1's result.** The Profile Extractor reads the
resume. The JD Analyzer reads the job description. They do not share output.
The first handoff is into agent 3, the Gap Analyst, which receives both.

There is no Python line that copies one agent's text into the next function
call. CrewAI does it because later tasks list earlier tasks in `context=`.

### Where the four UI values come from

The button passes four Gradio values, in this order (`app.py:396-401`):

| Argument | Widget | Becomes |
|----------|--------|---------|
| `resume_file` | uploaded PDF/DOCX/TXT | a file name inside `uploads/`, or `None` |
| `resume_text` | pasted resume | a string, or `None` |
| `jd_file` | uploaded posting | a file name inside `uploads/`, or `None` |
| `jd_text` | pasted posting | a string, or `None` |

`analyze` (`callbacks_analyze.py:135`) turns those into one request:

| Line | Call | Result |
|------|------|--------|
| **166** | `_resolve_resume(resume_file, resume_text)` | `(resume_path, pasted_resume)` |
| **179** | `_resolve_upload(jd_file, jd_text, "job description")` | `(jd_path, pasted_jd)` |
| **192** | `AnalysisRequest(...)` | the object the pipeline runs |

`_resolve_upload` (`callbacks_analyze.py:107`) is shared by both documents:

- **122-129** — an upload is checked, copied into `uploads/`, and only the **file name** is returned. Agents never see a full disk path.
- **130-131** — pasted text is kept as a string after `guardrails.redact_pii`.

Exactly one side of each pair is set. A file upload leaves the text argument `None`, and pasted text leaves the path `None`.

### The dict the crew actually receives

`_run_crew` (`pipeline.py:234`) builds that dict and starts the crew:

```startLine:242:257:careercrew/pipeline.py
    inputs = crew_inputs(
        resume_path=request.resume_path if not request.resume_text else None,
        resume_text=request.resume_text,
        jd_path=request.jd_path if not request.jd_text else None,
        jd_text=request.jd_text,
        seniority=(
            request.seniority
            or "the seniority / years of experience signaled in the job description"
        ),
        revision_notes=(request.revision_notes or "").strip()
        or "(none — produce the initial package)",
    )
    started = time.perf_counter()
    crew = build_crew(verbose=False, on_task=on_task)
    # Already on a worker thread. kickoff is synchronous; do not wrap it again.
    result = crew.kickoff(inputs=inputs)
```

`crew_inputs` (`crew.py:164-191`) fills any missing key with a sentence such as
`"(none; use pasted resume_text)"`, so the task text can tell the agent which
source to use. `crew.kickoff(inputs=inputs)` at **line 257** is the moment the
resume and job description enter CrewAI. CrewAI substitutes `{resume_path}`,
`{resume_text}`, `{jd_path}`, and `{jd_text}` into `config/tasks.yaml`.

### Which agent receives which document

Only the first two agents have tools (`crew.py:96-97`, `with_mcp=True`). The
tools are `read_resume_tool` (`mcp_server/server.py:25`) and
`read_job_description_tool` (`mcp_server/server.py:34`). They call
`document_tools.read_resume` (`document_tools.py:97`) and
`read_job_description` (`document_tools.py:120`), which open the file inside
`uploads/`.

| Order | Agent | Task | Code | Given | Returns |
|------:|-------|------|------|-------|---------|
| 1 | Profile Extractor | `extract_profile` | `crew.py:103-108` | `{resume_path}` or `{resume_text}` (`tasks.yaml:5-16`) | `CandidateProfile` |
| 2 | JD Analyzer | `analyze_jd` | `crew.py:109-114` | `{jd_path}` or `{jd_text}` (`tasks.yaml:22-31`) | `JobRequirements` |
| 3 | Gap Analyst | `analyze_gaps` | `crew.py:115-121` | outputs of tasks 1 and 2 | `GapReport` |
| 4 | Feedback Writer | `write_feedback` | `crew.py:122-128` | output of task 3 | `FeedbackDraft` |
| 5 | Interview Prep Advisor | `build_prep_plan` | `crew.py:129-135` | outputs of tasks 1, 2, and 3 | `InterviewPrepPlan` |

Task 2 has **no** `context=` argument (`crew.py:109-114`). It does not see the
profile. The two readers run one after the other only because the crew is
`Process.sequential` (`crew.py:152`).

### The handoff: `context=` on the later tasks

This is the entire pipe between agents:

```startLine:115:135:careercrew/crew.py
    analyze_gaps = Task(
        name="analyze_gaps",
        config=tasks_cfg["analyze_gaps"],
        agent=gap_analyst,
        context=[extract_profile, analyze_jd],
        output_pydantic=GapReport,
    )
    write_feedback = Task(
        name="write_feedback",
        config=tasks_cfg["write_feedback"],
        agent=feedback_writer,
        context=[analyze_gaps],
        output_pydantic=FeedbackDraft,
    )
    build_prep_plan = Task(
        name="build_prep_plan",
        config=tasks_cfg["build_prep_plan"],
        agent=interview_prep_advisor,
        context=[extract_profile, analyze_jd, analyze_gaps],
        output_pydantic=InterviewPrepPlan,
    )
```

When `kickoff` finishes a task, CrewAI keeps that task's output. When it starts
a later task, it appends every task listed in `context` to that agent's prompt.

| Line | `context=` | What the agent is shown |
|------|------------|-------------------------|
| **119** | `[extract_profile, analyze_jd]` | the profile and the job requirements |
| **126** | `[analyze_gaps]` | the gap report only |
| **133** | `[extract_profile, analyze_jd, analyze_gaps]` | profile, requirements, and gaps. Not the feedback bullets. |

`memory=False` (`crew.py:155`) means nothing else is stored. These three lists
are the only way one agent's result reaches another.

```
resume file or paste ──> Agent 1 Profile Extractor ── CandidateProfile ──┐
                                                                         ├──> Agent 3 Gap Analyst ── GapReport ──> Agent 4 Feedback Writer
job file or paste    ──> Agent 2 JD Analyzer       ── JobRequirements ──┘                │
                                         Agent 1 + Agent 2 + Agent 3 ────────────────────┴──> Agent 5 Prep Advisor
```

### How the five results come back to the app

`kickoff` returns them in task order on `result.tasks_output`.
`_parse_crew_outputs` (`pipeline.py:267`) zips that list with `CREW_STAGES`
(`pipeline.py:81-87`):

| Index | Stage name | Model |
|------:|------------|-------|
| 0 | `profile` | `CandidateProfile` |
| 1 | `requirements` | `JobRequirements` |
| 2 | `gaps` | `GapReport` |
| 3 | `feedback` | `FeedbackDraft` |
| 4 | `prep_plan` | `InterviewPrepPlan` |

```startLine:270:278:careercrew/pipeline.py
    for stage, output in zip(CREW_STAGES, outputs, strict=False):
        parsed[stage] = extract_json(getattr(output, "raw", None))
    trace.add("crew.parsed", "pipeline", f"{len(outputs)} task outputs parsed")

    profile = _coerce_model(CandidateProfile, parsed.get("profile"))
    requirements = _coerce_model(JobRequirements, parsed.get("requirements"))
    gaps = _coerce_model(GapReport, parsed.get("gaps"))
    feedback = _coerce_model(FeedbackDraft, parsed.get("feedback"))
    prep_plan = _coerce_model(InterviewPrepPlan, parsed.get("prep_plan"))
```

`run_analysis` returns that bundle as a `PipelineResult` (`pipeline.py:469`).
The UI reads it from `StopIteration.value` at `callbacks_analyze.py:212-213`.
The last yield (`callbacks_analyze.py:240-255`) draws the match report from the
gap and feedback models and the prep tab from the prep plan.

---

## 1. The wiring (where the click is bound)

| Step | File | Line | What it does |
|------|------|------|--------------|
| 1 | `app.py` | **380** | `analyze_outputs = [named[name] for name in OUTPUT_ORDER]` — builds the ordered output list once |
| 2 | `app.py` | **396** | `run_btn.click(analyze, inputs=..., outputs=analyze_outputs, show_progress="hidden")` |

```startLine:396:401:app.py
        run_btn.click(
            analyze,
            inputs=[resume_file, resume_text, jd_file, jd_text],
            outputs=analyze_outputs,
            show_progress="hidden",
        )
```

**Why `show_progress="hidden"`:** this generator updates 14 outputs. Gradio's
default "full" progress mode draws an accent border around *every* output on
*every* yield, so the borders stack into stray blue rules after the first few
progress ticks. The custom stage tracker replaces that chrome.

**Inputs are positional** and must match the signature order — that is why the
four inputs are `resume_file, resume_text, jd_file, jd_text` and not grouped by
kind. This is a real coupling; changing the signature means changing this line.

**Outputs are named, not magic indexes.** `OUTPUT_ORDER` in
`careercrew/ui_state.py:15` is the single source of truth for the tuple order,
and `AnalyzeOutputs.as_tuple()` (`ui_state.py:60`) builds the tuple from named
fields. No handler anywhere uses `outputs[4]`-style indexing.

---

## 2. Entry: the generator starts

```startLine:135:139:careercrew/callbacks_analyze.py
def analyze(
    resume_file, resume_text, jd_file, jd_text
) -> Iterator[tuple]:
    """Generator callback: streams live stage progress, then the final results."""
    view = _empty_outputs()
```

| Line | Detail |
|------|--------|
| **135** | Definition. Returns `Iterator[tuple]` — it is a generator, not a plain function. |
| **139** | `view = _empty_outputs()` builds a blank `AnalyzeOutputs` once, then reuses it via `view.apply(...)` for every yield. |

`_empty_outputs()` is at **`callbacks_analyze.py:51`**. It sets the idle status
text (`_IDLE_STATUS`, line **47**), renders the stepper idle (`_stages_html(-1)`),
and clears both result tabs. Every early return uses this same object so the
reset state is defined in exactly one place.

Inside the function there is a local helper:

```startLine:141:151:careercrew/callbacks_analyze.py
    def fail(message: str, *, status: str = "Couldn’t finish — see the message above.") -> tuple:
        return view.apply(
            error=_alert_html(message, kind="error"),
            status=status,
            stages=_stages_html(-1),
            approve=gr.update(interactive=False),
            reject=gr.update(interactive=False),
            revise=gr.update(interactive=False),
            run_button=gr.update(interactive=True),
            clear_button=gr.update(interactive=True),
        )
```

`fail()` is the single error exit: it shows an alert, resets the stepper, and —
importantly — **re-enables** the run and clear buttons (lines **149-150**).
Without that, a failed run would leave the page permanently stuck because the
button was disabled at the start.

---

## 3. The very first yield (why the click never looks dead)

```startLine:156:162:careercrew/callbacks_analyze.py
        yield view.apply(
            error="",
            status="**Starting…** checking your resume and job description.",
            stages=_stages_html(1, "Checking your inputs…"),
            run_button=gr.update(interactive=False),
            clear_button=gr.update(interactive=False),
        )
```

This runs **before** any file I/O or network call. Two jobs:

1. Paint stage 1 so the user sees movement immediately.
2. Disable `run_btn` (line **160**) — this is the fix for the double-click bug.
   The button is only re-enabled by `fail()` or by the final success yield.

---

## 4. Resolve the resume (line 166)

```startLine:166:166:careercrew/callbacks_analyze.py
            resume_path, pasted_resume = _resolve_resume(resume_file, resume_text)
```

`_resolve_resume` (**line 102**) is a thin wrapper over
`_resolve_upload(upload, pasted, kind)` (**line 107**). Both resume and JD go
through the same function so they behave identically.

What `_resolve_upload` does, in order:

| Line | Action |
|------|--------|
| **113-114** | Unwrap Gradio 6 quirks: a `File` may arrive as a path string, a tempfile object, or a **1-item list**. |
| **119-121** | Derive a filename via `getattr(upload, "name", ...)` when it is not a string. |
| **122** | `guardrails.check_upload(check_name)` — extension + 5 MB size check (`guardrails.py:46`). |
| **123-125** | `os.makedirs(upload_dir)` and compute `base = abspath(upload_dir)`. |
| **126** | **Path-traversal guard:** `if not destination.startswith(base + os.sep): raise ValueError`. |
| **128** | `shutil.copyfile(...)` into `uploads/`, then return **only the basename**. |
| **130-131** | No file? Use pasted text, passed through `guardrails.redact_pii` first. |

Two deliberate choices worth saying out loud:

- The agents receive a **basename**, not an absolute path. `document_tools`
  re-joins it against the uploads folder, so an agent cannot be tricked into
  reading `C:\Windows\...`.
- **PII is redacted before the text ever reaches a model** (`redact_pii`,
  `guardrails.py:39`). The file path is *not* redacted — the file is read later
  through MCP, where `document_tools` handles it.

### Empty-input guards (lines 171-189)

```startLine:171:189:careercrew/callbacks_analyze.py
        if resume_path is None and pasted_resume is None:
            yield fail(
                "Add a resume first — upload a PDF/DOCX/TXT file, or paste the text "
                "in the Paste text tab."
            )
            return

        try:
            jd_path, pasted_jd = _resolve_upload(jd_file, jd_text, "job description")
        except Exception as exc:  # noqa: BLE001 - surface a clean error
            yield fail(f"Job description error: {exc}", status="Job description rejected.")
            return

        if jd_path is None and pasted_jd is None:
            yield fail(
                "Add a job description — upload a PDF/DOCX/TXT file, or paste the "
                "posting text in the Paste posting tab."
            )
            return
```

Note the flow: `yield fail(...)` **then `return`**. `yield` alone would keep
the generator alive; the `return` ends it.

---

## 5. Build the request (line 192)

```startLine:192:199:careercrew/callbacks_analyze.py
        request = AnalysisRequest(
            package_id=make_package_id(),
            resume_path=resume_path,
            resume_text=pasted_resume,
            jd_path=jd_path,
            jd_text=pasted_jd,
            seniority="",
        )
```

| Field | Value |
|-------|-------|
| `package_id` | `make_package_id()` → `pkg-` + 8 hex chars (`pipeline.py:483`) |
| `resume_path` / `jd_path` | basenames inside `uploads/`, or `None` |
| `resume_text` / `jd_text` | redacted pasted text, or `None` |
| `seniority` | **always `""` here** — no UI picker exists |

`AnalysisRequest` is a dataclass at `pipeline.py:51`. The `seniority=""` is
intentional: the pipeline **infers** it from the job description at
`pipeline.py:358` via `infer_seniority_from_jd(jd_plain)`. Only the CLI can
override it.

---

## 6. Hand off to the worker thread (line 207)

```startLine:207:219:careercrew/callbacks_analyze.py
        stages_run = stream_with_progress(request, reading_detail="Reading your resume…")
        try:
            while True:
                try:
                    target, detail = next(stages_run)
                except StopIteration as finished:
                    result = finished.value
                    break
                yield view.apply(stages=_stages_html(target, detail), status=detail)
        except Exception as exc:  # noqa: BLE001 - surface a clean error, never crash
            logger.exception("analysis run failed")
            yield fail(str(exc) or "Analysis failed unexpectedly.")
            return
```

This is the part that trips people up, so it is worth explaining slowly.

### `stream_with_progress` (`runner.py:58`)

It is a generator that **spawns a thread, then polls it**:

```startLine:90:105:careercrew/runner.py
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_analysis, request, progress=progress, on_task=on_task)
        expected = 2
        last_yielded = 1
        while not future.done():
            reported = int(stages["index"])  # type: ignore[arg-type]
            if reported >= expected:
                expected = reported + 1
            target = min(expected, TOTAL_STAGES)
            if target != last_yielded:
                last_yielded = target
                detail = str(stages["detail"] or "Working…")
                yield target, detail
            wait_futures([future], timeout=1.0)
        result: PipelineResult = future.result()
    return result
```

- **Line 91** — `pool.submit(run_analysis, ...)`. The pipeline runs on a
  **worker thread**, so Gradio's event loop stays free to push updates to the
  browser. If this ran inline, the UI would freeze for the whole crew run.
- **Line 103** — poll roughly once per second (`wait_futures([future], timeout=1.0)`).
- **Line 105** — `future.result()` re-raises any exception from the thread on
  the main thread, so the caller's `except` block can catch it.

### How `StopIteration.value` works (callbacks_analyze.py:213)

A generator cannot `return` a value through `yield`, but Python stores the
return value on the `StopIteration` object. So:

```python
except StopIteration as finished:
    result = finished.value      # ← the PipelineResult
```

That is the **only** way the result comes back to the UI. Everything else the
loop sees is a `(stage_number, detail)` pair used purely for the stepper.

### Two state channels

`careercrew/runner.py` keeps a small dict, `stages` (line **68**), that two callbacks mutate:

| Callback | Line | Trigger |
|----------|------|---------|
| `progress(message)` | **70** | Text from `run_analysis` (`notify(...)`) |
| `on_task(output)` | **81** | After each of the 5 CrewAI tasks fire |

`on_task` maps the CrewAI agent name to a stepper number via `AGENT_STAGE`
(**line 42**) and the task name via `TASK_STAGE` (**line 49**):

| CrewAI agent | Task | Stage | Stepper label |
|--------------|------|-------|---------------|
| `Profile Extractor` | `extract_profile` | 2 | Read resume |
| `JD Analyzer` | `analyze_jd` | 3 | Understand role |
| `Gap Analyst` | `analyze_gaps` | 4 | Score match |
| `Feedback Writer` | `write_feedback` | 5 | Draft rewrites |
| `Interview Prep Advisor` | `build_prep_plan` | 6 | Prep plan |

`FINAL_STAGE = int(Stage.PREP) + 1` (**line 39**) = 7, a sentinel meaning "all
six done".
---

## 7. Inside the pipeline: `run_analysis`

Everything from here runs **on the worker thread**.
Signature at `pipeline.py:291`.

### 7.1 Phase 1 — validate inputs (line 317)

```startLine:317:325:careercrew/pipeline.py
    check = guardrails.validate_request(
        resume_path=request.resume_path,
        resume_text=request.resume_text,
        jd_path=request.jd_path,
        jd_text=request.jd_text,
    )
    if not check.ok:
        trace.add("guardrail.input", "guardrails", "; ".join(check.errors), status="error")
        raise ValueError("; ".join(check.errors))
```

`validate_request` (`guardrails.py:65`) enforces **exactly one** source per
input — a file *or* pasted text, never both (lines **82** and **97**). It also
checks minimum pasted length (`MIN_PASTED_RESUME_CHARS`, line **87**) and scans
for prompt-injection patterns (`_DISALLOWED_INPUT`, line **111**).

If validation fails it raises `ValueError`, which propagates out of the thread
and is caught at `callbacks_analyze.py:216` → `fail(...)`.

### 7.2 Fail-fast text reads (lines 331-353)

```startLine:331:353:careercrew/pipeline.py
    try:
        _prepare_resume_text(request)
    except JobDescriptionError:
        raise
    except Exception as exc:  # noqa: BLE001
        trace.add("input.resume", "pipeline", f"{type(exc).__name__}: {exc}", status="error")
        raise ValueError(f"Could not read the resume: {exc}") from exc

    # Validate the JD here so the error surfaces before the crew. Call the
    # document tool directly (not through MCP) so the original
    # JobDescriptionError message is preserved for the UI.
    try:
        jd_plain = _prepare_jd_text(request)
        trace.add("input.jd", "pipeline", "job description read")
    except JobDescriptionError as exc:
        trace.add("input.jd", "pipeline", str(exc), status="error")
        raise
    except Exception as exc:  # noqa: BLE001
        trace.add("input.jd", "pipeline", f"{type(exc).__name__}: {exc}", status="error")
        raise JobDescriptionError(
            "The job description could not be read. Upload a PDF/DOCX/TXT file "
            "or paste the job description text instead."
        ) from exc
```

Both helpers are thin: `_prepare_resume_text` (**line 216**) and
`_prepare_jd_text` (**line 225**) just dispatch to `document_tools`.

**The crucial detail is the comment at line 339-341.** The JD is read *here*,
directly, rather than only inside the crew via MCP, for two reasons:

1. A corrupt PDF fails in ~50 ms instead of after a minute of agent work.
2. Going through MCP would wrap the original `JobDescriptionError` in a tool
   error string, so the user would lose the specific explanation. Calling the
   function directly preserves the message.

### 7.3 Infer seniority (line 358)

```startLine:357:364:careercrew/pipeline.py
    if not (request.seniority or "").strip():
        request.seniority = infer_seniority_from_jd(jd_plain)
        if request.seniority:
            trace.add(
                "input.seniority",
                "pipeline",
                f"inferred from JD: {request.seniority}",
            )
```

`infer_seniority_from_jd` lives in `models.py` (function at **line 205**) and
returns one of `2-3 years`, `5-10 years`, `10+ years`, or `""`. It reads the
years-of-experience phrases in the posting. Used later by the prep plan.

### 7.4 Phase 2 — run the crew (lines 378-396)

```startLine:378:395:careercrew/pipeline.py
    if settings.has_llm:
        notify("Running the five-agent crew (this can take a minute)...")
        try:
            crew_result = _run_crew(request, trace, notify, on_task)
            parsed = _parse_crew_outputs(crew_result, request, trace)
            profile = parsed["profile"]
            requirements = parsed["requirements"]
            gaps = parsed["gaps"]
            feedback = parsed["feedback"]
            prep_plan = parsed["prep_plan"]
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash the UI
            logger.warning("crew run failed: %s", exc)
            trace.add("crew.error", "crew", f"{type(exc).__name__}: {exc}", status="error")
            warnings.append("The agent crew did not complete; using the gap-based fallback.")
            used_fallback = True
    else:
        warnings.append("No OPENAI_API_KEY set; running the gap-based fallback only.")
        used_fallback = True
```

`settings.has_llm` (`config.py:55`) is just `bool(self.openai_api_key)`. **No key
→ the crew is skipped entirely**, not attempted and failed.

The `except` is deliberately broad (`noqa: BLE001`): a live API can fail in many
ways (rate limit, timeout, bad JSON, model change). The app degrades to the
fallback rather than losing the user's work.

### 7.5 `_run_crew` (line 234)

```startLine:234:257:careercrew/pipeline.py
def _run_crew(
    request: AnalysisRequest,
    trace: ExecutionTrace,
    notify: ProgressFn,
    on_task: TaskCallback | None = None,
):
    from careercrew.crew import build_crew, crew_inputs

    inputs = crew_inputs(
        resume_path=request.resume_path if not request.resume_text else None,
        resume_text=request.resume_text,
        jd_path=request.jd_path if not request.jd_text else None,
        jd_text=request.jd_text,
        seniority=(
            request.seniority
            or "the seniority / years of experience signaled in the job description"
        ),
        revision_notes=(request.revision_notes or "").strip()
        or "(none — produce the initial package)",
    )
    started = time.perf_counter()
    crew = build_crew(verbose=False, on_task=on_task)
    # Already on a worker thread. kickoff is synchronous; do not wrap it again.
    result = crew.kickoff(inputs=inputs)
```

Two things to explain:

- **The `import` is inside the function** (line 240). `crewai` is heavy; importing
  it lazily keeps `main.py --help` and the test suite fast, and keeps the offline
  path free of the dependency.
- **Line 256** ("Already on a worker thread…") documents a real
  trap: `crew.kickoff()` is synchronous. Wrapping it in *another* thread here
  would break the `on_task` callbacks' ordering and add a thread per run for
  nothing.

### 7.6 `build_crew` (`crew.py:57`)

| Line | Detail |
|------|--------|
| **74** | `mcp_server = crewai_mcp_server()` — one server config shared by both reader agents |
| **75-78** | Load `resume_guidelines.md` and `interview_guidelines.md` as **real** `StringKnowledgeSource` objects (content, not a path, so cwd does not matter) |
| **96-100** | Five agents; only `profile_extractor` and `jd_analyzer` get `with_mcp=True` |
| **103-135** | Five tasks, each with `output_pydantic=` set to its model (e.g. line **107**) |
| **139-161** | `Crew(...)` with `process=Process.sequential` (line **152**), `memory=False` (line **155**) |

`max_iter` differs by agent: readers get **6** (they must call a tool, then
answer — two rounds), writers get **4** (they only transform the previous
task's output). This stops a stuck tool call from spinning 25 times.

`memory=False` (line **155**) is a cost decision: task context already passes
each result forward, so enabling Crew memory would add one embedding/model call
per agent for data that is already handed over.

**Context edges** (lines **119, 126, 133**) are what make the order meaningful.
Section 0a is the full handoff. The picture:
```
extract_profile ─┬─> analyze_gaps ─> write_feedback
analyze_jd ──────┘         │
        └──────────> build_prep_plan <┘
```

### 7.7 `_parse_crew_outputs` (line 267)

```startLine:270:272:careercrew/pipeline.py
    for stage, output in zip(CREW_STAGES, outputs, strict=False):
        parsed[stage] = extract_json(getattr(output, "raw", None))
    trace.add("crew.parsed", "pipeline", f"{len(outputs)} task outputs parsed")
```

- **`strict=False`** matters: if the crew returned fewer tasks than expected
  (an agent bailed), `zip` truncates instead of raising, and the missing models
  stay `None` → fallback fills them.
- `extract_json` (**line 93**) strips Markdown fences, then falls back to
  brace-matching, then returns `None`. Models are **not validated as JSON
  only** — the model may wrap its answer in prose.
- `_coerce_model` (**line 116**) wraps `model_validate` in `try/except` and
  returns `None` on failure. A malformed agent answer degrades; it does not crash.
### 7.8 Revision-notes merge (lines 412-428)

```startLine:412:428:careercrew/pipeline.py
    if (request.revision_notes or "").strip():
        profile, gaps, requirements = _apply_revision_experience(
            profile, gaps, requirements, request
        )
        if feedback is None:
            feedback = FeedbackDraft(
                rewritten_bullets=[
                    RewrittenBullet(
                        text=f"Highlight attested experience: {(request.revision_notes or '')[:180]}",
                        cited_fact=(request.revision_notes or "")[:240],
                    )
                ],
                talking_points=[
                    f"Be ready to discuss: {(request.revision_notes or '')[:160]}",
                ],
            )
        warnings.append("Candidate-attested Request changes updates were applied to experience.")
```

This is **skipped on a first Analyze** because `revision_notes` is empty. It
only matters on the "Apply updates & re-analyze" path. `_apply_revision_experience`
(**line 126**) appends a `WorkExperience` marked `Candidate-attested update` and
promotes requirements the notes cover from `out_of_scope` to `covered`.

### 7.9 Prep plan fallback (line 432)

```startLine:432:445:careercrew/pipeline.py
    if prep_plan is None:
        from careercrew.prep import build_fallback_plan

        # Prefer JD-extracted requirements.seniority when the crew produced it.
        reqs = requirements or JobRequirements()
        effective_seniority = (reqs.seniority or request.seniority or "").strip()
        prep_plan = build_fallback_plan(
            profile or CandidateProfile(),
            reqs,
            gaps or GapReport(),
            effective_seniority,
        )
        if settings.has_llm:
            warnings.append("Interview prep plan used the deterministic gap-based fallback.")
```

Only the **prep plan** has a deterministic fallback. The profile, requirements,
and gap report have none — they stay empty, which is why the match report shows
"Nothing here yet" offline. This is the honesty constraint: the fallback cannot
invent resume facts it never read.

### 7.10 Phase 4 — output guardrails (lines 450-465)

```startLine:450:467:careercrew/pipeline.py
    validation = guardrails.validate_package(package, feedback, profile)
    warnings.extend(validation.warnings)
    if not validation.ok:
        trace.add("guardrail.output", "guardrails", "; ".join(validation.errors), status="error")
        raise ValueError("Prep bundle failed output guardrails: " + "; ".join(validation.errors))
    trace.add("guardrail.output", "guardrails", "prep bundle validated")

    plan_problems = guardrails.validate_prep_plan(prep_plan, gaps or GapReport(), requirements)
    if plan_problems:
        trace.add(
            "guardrail.prep", "guardrails", "; ".join(plan_problems), status="warning"
        )
        warnings.extend(plan_problems)
    else:
        trace.add("guardrail.prep", "guardrails", "prep plan validated")

    if used_fallback:
        warnings.append("Run used the gap-based fallback instead of the agent crew.")
```

Note the asymmetry — this is a designed distinction, not an oversight:

| Check | On failure |
|-------|-----------|
| `validate_package` | **raise** → nothing shown (fail closed) |
| `validate_prep_plan` | **warning only** → plan still shown |

A package with an uncited bullet is a honesty failure, so it must not ship. A
prep plan with a soft priority label is still usable advice, so it ships with a
warning.

### 7.11 Return (line 469)

```startLine:469:480:careercrew/pipeline.py
    return PipelineResult(
        package=package,
        profile=profile or CandidateProfile(),
        requirements=requirements or JobRequirements(),
        gaps=gaps or GapReport(),
        feedback=feedback or FeedbackDraft(),
        prep_plan=prep_plan,
        trace=trace,
        request=request,
        warnings=warnings,
        used_fallback=used_fallback,
    )
```

Each `... or DefaultModel()` guarantees the caller never handles `None`. That
return value travels back through `future.result()` (`runner.py:104`) and out
of the generator as `StopIteration.value`.

---

## 8. Back in the callback: save for review (line 221)

```startLine:221:231:careercrew/callbacks_analyze.py
        _REVIEW.submit_for_review(
            {
                "resume_path": request.resume_path,
                "resume_text": request.resume_text,
                "jd_path": request.jd_path,
                "jd_text": request.jd_text,
                "seniority": request.seniority,
            },
            result.package,
            result.trace,
        )
```

`_REVIEW` comes from `careercrew/services.py:14` (`REVIEW = PackageReviewService(STORE)`).
`STORE` is a `SessionStore` over SQLite (line **13**).

`submit_for_review` is at **`review.py:64`**. It does two writes:

| Line | Call | Effect |
|------|------|--------|
| **74** | `self._store.save_package(...)` → `session_store.py:119` | UPSERT the package row |
| **75** | `self._store.update_status(package_id, PENDING_REVIEW, ...)` → `session_store.py:175` | Flip status |

`submit_for_review` also calls `_check_transition(status, PENDING_REVIEW)` first
(line **73**), which is why a package already `APPROVED` cannot be resubmitted.

**Why this matters for the user:** the inputs are saved *with* the package. That
is exactly what makes "Apply updates & re-analyze" possible later — the revision
path re-reads `stored.get("inputs")` at `callbacks_analyze.py:453` to recover
the resume and JD without asking the user to re-upload.

---

## 9. The final yield — how you "get the result" (line 240)

```startLine:233:255:careercrew/callbacks_analyze.py
        mode = " (limited mode)" if result.used_fallback else ""
        status = (
            f"**Your prep bundle is ready{mode}.** "
            f"`{result.package.package_id}` · "
            f"{len(result.prep_plan.focus_areas)} prep focus area(s) · "
            f"{len(result.package.do_not_claim)} item(s) still need your input."
        )
        yield view.apply(
            error="",
            status=status,
            stages=_stages_html(_FINAL, "All set — review your match report, prep plan, and answers."),
            match_report=_insight_html(result),
            prep_plan=_prep_html(result.prep_plan),
            approve=gr.update(interactive=True),
            reject=gr.update(interactive=True),
            revise=gr.update(interactive=True),
            package=result.package.model_dump(),
            notes=gr.update(value="", interactive=True),
            context=_serialize_result(result),
            review_guide=_review_guide_html("ready", package_id=result.package.package_id),
            run_button=gr.update(interactive=True),
            clear_button=gr.update(interactive=True),
        )
```

This single yield is the answer to "how do I get the final result". Field by field:

| Field | Rendered by | What the user sees |
|-------|-------------|--------------------|
| `status` | Markdown box | "Your prep bundle is ready · `pkg-…` · 3 focus areas · 1 item needs input" |
| `stages` | `_stages_html(_FINAL, ...)` (`ui_html.py:61`) | All 6 steps ticked, 6/6 |
| `match_report` | `_insight_html(result)` (`ui_html.py:122`) | Coverage score, verdict table, bullet rewrites, talking points, do-not-claim list |
| `prep_plan` | `_prep_html(result.prep_plan)` (`ui_html.py:275`) | Seniority band + ranked focus areas |
| `approve` / `reject` / `revise` | `gr.update(interactive=True)` | The three decision buttons light up |
| `package` | `result.package.model_dump()` | Dict in Gradio state; later feeds Approve/Reject |
| `context` | `_serialize_result(result)` (`callbacks_analyze.py:62`) | JSON blob for the coach and interview tabs |
| `review_guide` | `_review_guide_html("ready", ...)` (`ui_html.py:337`) | Decision dock instructions |
| `run_button` | `interactive=True` (line **253**) | **Re-enabled** — the run is over |

`_serialize_result` (line **62**) is what makes the rest of the app work: it
packs `package_id`, `profile`, `requirements`, `gaps`, and `prep_plan` into one
JSON string. The Prep coach, Mock interview, and Post-interview coach all read
that string later through `_load_context` (**line 75**) and `_context_models`
(**line 88**) — which is why those tabs can work without re-running Analyze.

---

## 10. One-page summary

```
CLICK (app.py:396)
  └─> analyze()                                   callbacks_analyze.py:135
        ├─ yield stage 1, disable run button      :156
        ├─ _resolve_resume → _resolve_upload      :166 / :107
        │     check_upload, path guard, copy      guardrails.py:46
        ├─ AnalysisRequest(package_id=pkg-…)       :192
        ├─ stream_with_progress()                 :207 → runner.py:58
        │     ├─ ThreadPoolExecutor.submit        runner.py:91
        │     │    └─ run_analysis                pipeline.py:291
        │     │          ├─ validate_request      :317  (→ guardrails.py:65)
        │     │          ├─ _prepare_resume_text  :332  (fail fast)
        │     │          ├─ _prepare_jd_text      :343  (fail fast)
        │     │          ├─ infer_seniority_from_jd :358
        │     │          ├─ _run_crew             :381 → :234
        │     │          │     └─ build_crew      crew.py:57
        │     │          │           └─ kickoff   5 agents, sequential
        │     │          ├─ _parse_crew_outputs   :267
        │     │          ├─ build_fallback_plan   :432  (if no key/fail)
        │     │          ├─ validate_package      :450  (fail closed)
        │     │          └─ return PipelineResult :469
        │     ├─ poll every 1s → yield (stage,detail)
        │     └─ StopIteration.value → result     :104
        ├─ _REVIEW.submit_for_review              :221 → review.py:64
        │     └─ SQLite: save_package + PENDING_REVIEW
        └─ FINAL YIELD                            :240
              status / stages 6-of-6 / match_report / prep_plan
              buttons enabled / package / context / review_guide
              run button re-enabled
```

---

## 11. Questions you will likely be asked

**"Why a generator instead of a normal function?"**
Because the crew takes 30-90 seconds. A generator can `yield` intermediate
updates, so the stepper animates. A plain function would freeze the UI for the
whole run and then paint once.

**"Why a separate thread?"**
`crew.kickoff()` is blocking. On the worker thread the Gradio event loop stays
responsive, so the polling loop can push progress updates to the browser.

**"How does the result get out of the generator?"**
Through `StopIteration.value`. `stream_with_progress` returns the
`PipelineResult`; the caller catches `StopIteration` and reads `.value`.

**"What if there is no API key?"**
`settings.has_llm` is `False`, the crew block is skipped, and only the prep
plan is built deterministically. The match report stays empty — deliberately,
because the fallback has not read the resume and must not invent facts.

**"What if the crew returns garbage JSON?"**
`extract_json` returns `None`, `_coerce_model` returns `None`, the model stays
`None`, and the fallback or defaults fill in. It never raises on a bad parse.

**"Where does the double-submit protection come from?"**
Line **160**: `run_button=gr.update(interactive=False)` in the first yield.
Every exit path (`fail()` line **149**, final yield line **253**) re-enables it.

**"Why is the JD read twice — here and inside the crew?"**
Here for fast failure and a preserved error message; inside the crew via MCP
because the JD Analyzer agent is required to use the MCP tool. The double read
is intentional (see the comment at `pipeline.py:339`).

---

## 12. Related docs

- [`CODE_PATH_ANALYZE.md`](CODE_PATH_ANALYZE.md) — diagram-heavy version, same path
- [`CODE_PATH_HITL.md`](CODE_PATH_HITL.md) — what Approve / Apply updates / Reject do next
- [`CODE_PATH_PREP.md`](CODE_PATH_PREP.md) — how the prep plan is built
- [`code-walkthrough/pipeline.md`](code-walkthrough/pipeline.md) — per-function notes
- [`code-walkthrough/app.md`](code-walkthrough/app.md) — page layout and wiring
