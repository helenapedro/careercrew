# CareerCrew architecture — diagrams and quick explanations

> A one-page-per-diagram tour of how CareerCrew is built. Every diagram is
> followed by a short "what to notice" paragraph so the picture is usable
> without reading the code first.
>
> Deeper material:
> - `ARCHITECTURE.md` — the prose architecture with the design decisions
> - `docs/ANALYZE_BUTTON_WALKTHROUGH.md` — one continuous trace with full code
> - `docs/code-walkthrough/INDEX.md` — per-file reference pages

All line numbers in this document were checked against the working tree with
`python tools/verify_doc_refs.py docs/ARCHITECTURE_DIAGRAMS.md`.

---

## 1. System context — who talks to what

CareerCrew is one Python process plus one external API. There is no second
service to deploy: the MCP server runs as a stdio child process of the same
app, and SQLite is a file on disk.

```mermaid
flowchart TB
    subgraph USER["Candidate (browser)"]
        B["Clicks buttons in the Gradio page"]
    end

    subgraph APP["One Python process — python app.py, 0.0.0.0:7860"]
        UI["app.py<br/>Gradio layout + event wiring"]
        CB["callbacks_analyze.py · callbacks_interview.py<br/>one callback per button"]
        RUN["runner.py<br/>single-worker ThreadPoolExecutor"]
        PIPE["pipeline.py<br/>run_analysis"]
        CREW["crew.py → CrewAI<br/>5 sequential agents"]
        PREP["prep.py<br/>deterministic prep plan"]
        GR["guardrails.py<br/>input + output checks"]
        COACH["coach.py · interview.py<br/>coaches and mock interviewer"]
        MCPC["mcp_client.py"]
    end

    subgraph LOCAL["Local subprocess"]
        MCP["mcp_server/server.py<br/>FastMCP over stdio"]
        DT["document_tools.py<br/>PDF / DOCX / TXT → text"]
    end

    subgraph DISK["Filesystem"]
        DB[("careercrew.db<br/>SQLite")]
        UP["uploads/<br/>confined upload folder"]
        K["knowledge/*.md<br/>agent guidelines"]
    end

    OPENAI["OpenAI API<br/>chat · whisper-1 · tts-1"]

    B --> UI --> CB --> RUN --> PIPE
    PIPE --> GR
    PIPE --> CREW
    PIPE --> PREP
    CREW --> MCPC --> MCP --> DT
    PIPE --> DT
    DT --> UP
    CREW --> K
    CREW --> OPENAI
    COACH --> OPENAI
    CB --> COACH
    CB --> DB
    PIPE --> DB
```

**What to notice**

- **One process, one port.** `app.py` serves everything; the MCP server is a
  stdio child, not an HTTP service (`careercrew/mcp_client.py:53-66`).
- **Two paths reach the same document code.** The agents go through MCP
  (`mcp_server/server.py:25-37`); the pre-flight check in the pipeline calls
  `document_tools.py` directly so the original error message survives
  (`careercrew/pipeline.py:231-237`). Both end in the same reader, so there is
  no second implementation to keep in sync.
- **Everything that costs a model call is inside `OPENAI`**, which is why the
  app still runs with no key (§7).

---

## 2. Layered view — which module owns which decision

The layers are strict: a lower layer never imports a higher one. The import
graph confirms it, so this is an acyclic design, not just a drawing.

```mermaid
flowchart TB
    subgraph L4["Layer 4 · Presentation"]
        L4A["app.py<br/>page, tabs, button wiring"]
        L4B["ui_html.py · ui_css.py · ui_state.py"]
        L4C["callbacks_analyze.py · callbacks_interview.py"]
    end

    subgraph L3["Layer 3 · Orchestration and practice"]
        L3A["runner.py<br/>worker thread + Stage"]
        L3B["pipeline.py<br/>run_analysis"]
        L3C["prep.py · interview.py · coach.py"]
    end

    subgraph L2["Layer 2 · Agents, tools, and policy"]
        L2A["crew.py<br/>build_crew, crew_inputs"]
        L2B["mcp_client.py · mcp_server/server.py"]
        L2C["document_tools.py<br/>extraction"]
        L2D["guardrails.py<br/>input and output checks"]
    end

    subgraph L1["Layer 1 · State and contracts"]
        L1A["models.py<br/>Pydantic contracts"]
        L1B["review.py<br/>HITL state machine"]
        L1C["session_store.py<br/>SQLite"]
        L1D["config.py · services.py<br/>settings and singletons"]
        L1E["llm.py · audio.py<br/>OpenAI helpers"]
    end

    L4C --> L3A
    L4C --> L3B
    L4C --> L3C
    L4A --> L4C
    L3A --> L3B
    L3B --> L2A
    L3B --> L2B
    L3B --> L2C
    L3B --> L2D
    L3C --> L2D
    L2A --> L1A
    L2C --> L2D
    L2B --> L2C
    L3B --> L1B
    L1B --> L1C
    L3C --> L1E
```

**What to notice**

- **Only callbacks know about Gradio.** `pipeline.py`, `crew.py`, and
  `session_store.py` never import `gradio`, so the CLI (`main.py`) reuses the
  same pipeline with no UI present.
- **`guardrails.py` is a leaf that only depends on `models.py`.** That is what
  lets it be called from five different places without a cycle (§6).
- **`services.py` is 12 lines of wiring** (`careercrew/services.py`): it opens
  one `SessionStore` and one `PackageReviewService` at import time, so the UI
  never constructs a second database handle.

---

## 3. The analysis run — request to validated bundle

This is the diagram to show first. It is the whole "Analyze match" press in one
picture. Exact code for each step is in `docs/ANALYZE_BUTTON_WALKTHROUGH.md`.

```mermaid
sequenceDiagram
    autonumber
    actor U as Candidate
    participant UI as app.py<br/>run_btn.click
    participant CB as callbacks_analyze.analyze
    participant R as runner.stream_with_progress
    participant P as pipeline.run_analysis
    participant G as guardrails
    participant DT as document_tools
    participant C as crew.py + CrewAI
    participant M as MCP server
    participant DB as session_store

    U->>UI: press "Analyze match"
    UI->>CB: analyze(resume_file, resume_text, jd_file, jd_text)
    CB-->>UI: yield "Starting…" (buttons disabled)

    Note over CB: Step 1 — resolve inputs
    CB->>G: check_upload(name) for each uploaded file
    CB->>G: redact_pii(pasted_text)
    CB->>CB: build AnalysisRequest(package_id=…)

    Note over CB,R: Step 2 — hand off to a worker thread
    CB->>R: stream_with_progress(request)
    R->>P: pool.submit(run_analysis, …)
    loop until the future is done
        R-->>CB: yield (stage_index, detail)
        CB-->>UI: re-render the stage tracker
    end

    Note over P: Phase 1 — validate, fail fast
    P->>G: validate_request(resume + jd sources)
    G-->>P: errors → ValueError (run stops here)
    P->>DT: read the resume and JD to plain text
    P->>P: infer_seniority_from_jd(jd_plain)

    Note over P,C: Phase 2 — five agents, sequential
    P->>C: build_crew() then crew.kickoff(inputs=crew_inputs(…))
    C->>M: read_resume_tool / read_job_description_tool
    M->>DT: shared extraction code
    DT-->>M: text
    Note right of C: 1 Profile, 2 JD, 3 Gap<br/>4 Feedback, 5 Prep
    C-->>P: result.tasks_output (5 raw outputs)

    Note over P: Phase 3 — parse into typed models
    P->>P: _parse_crew_outputs → profile, requirements,<br/>gaps, feedback, prep_plan
    alt crew raised, or no API key
        P->>P: build_fallback_plan(...) + warnings
    end

    Note over P,G: Phase 4 — output guardrails, fail closed
    P->>G: validate_package(package, feedback, profile)
    G-->>P: error → ValueError (bundle not shown)
    P->>G: validate_prep_plan(plan, gaps, requirements)
    G-->>P: problems → warnings only
    P-->>R: PipelineResult

    Note over CB,DB: Step 3 — persist as PENDING_REVIEW
    CB->>DB: REVIEW.submit_for_review(inputs, package, trace)
    CB->>CB: _serialize_result(result) → ctx_state
    CB-->>UI: final yield: report, prep plan, package, ctx_state

    U->>U: approves, rejects, or requests changes (§5)
```

**What to notice**

- **The thread hop is the part people miss.** `analyze` is a generator that
  runs on the Gradio event thread; the actual work runs on a single-worker
  pool so the page can still stream progress (`careercrew/runner.py:58-105`).
- **Fail closed vs warn.** A `validate_request` or `validate_package` failure
  raises and shows nothing; a `validate_prep_plan` failure only adds a warning
  (`careercrew/pipeline.py:394-398`, `careercrew/pipeline.py:455-465`).
- **Fallback is a real branch, not an error page.** The same function ends with
  a usable `PipelineResult` whether the crew ran or not
  (`careercrew/prep.py:81-145`, merge at `careercrew/pipeline.py:418-434`).
- **`ctx_state` is what makes tabs 2-4 possible.** `_serialize_result` stores
  the models as JSON so the coaches and mock interviewer can reload them
  without re-running the crew (`careercrew/callbacks_analyze.py:61-71`).

---

## 4. Agent pipeline and the handoff mechanism

The five agents are sequential and share no memory. Each task declares the
earlier tasks it needs in `context=`, and CrewAI injects those outputs into the
prompt. That is the entire handoff mechanism.

```mermaid
flowchart LR
    IN["crew_inputs()<br/>paths, pasted text,<br/>seniority, revision_notes"]

    subgraph CREW["Crew(process=Process.sequential, memory=False)"]
        direction LR
        A1["1 · Profile Extractor<br/>max_iter 6, MCP on"]
        A2["2 · JD Analyzer<br/>max_iter 6, MCP on"]
        A3["3 · Gap Analyst<br/>max_iter 4"]
        A4["4 · Feedback Writer<br/>max_iter 4"]
        A5["5 · Interview Prep Advisor<br/>max_iter 4"]
    end

    O1["CandidateProfile"]
    O2["JobRequirements"]
    O3["GapReport"]
    O4["FeedbackDraft"]
    O5["InterviewPrepPlan"]

    K["knowledge/<br/>resume_guidelines.md<br/>interview_guidelines.md"]

    IN --> A1
    A1 --> O1
    A2 --> O2
    O1 --> A3
    O2 --> A3
    A3 --> O3
    O3 --> A4
    O4 --> A4
    O1 --> A5
    O2 --> A5
    O3 --> A5
    A5 --> O5
    K -.embedded once.-> CREW
```

Task wiring, quoted from the code:

```126:146:careercrew/crew.py
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

**What to notice**

- **`context=` is the arrow you are looking for.** `analyze_gaps` receives the
  profile and the requirements because both tasks are listed;
  `write_feedback` receives only the gaps.
- **`output_pydantic=` gives every handoff a typed shape.** Models live in
  `careercrew/models.py` (`CandidateProfile`, `JobRequirements`, `GapReport`,
  `FeedbackDraft`, `InterviewPrepPlan`).
- **Only the two readers get MCP.** They are the ones that must read a file
  (`max_iter=6`); the other three write from the previous task and stop at 4.
- **`memory=False` is deliberate.** Because `context=` already passes the
  outputs, CrewAI memory would only add an extra model call per agent.

---

## 5. HITL review — the state machine and the approval gate

Analysis never auto-approves. The bundle is persisted as `PENDING_REVIEW`, and
the practice tabs refuse to run until a human approves it.

```mermaid
stateDiagram-v2
    [*] --> DRAFT : run_analysis returned a validated bundle
    DRAFT --> PENDING_REVIEW : submit_for_review()
    PENDING_REVIEW --> APPROVED : Approve prep bundle
    PENDING_REVIEW --> REJECTED : Reject
    PENDING_REVIEW --> DRAFT : Request changes<br/>(revision_count += 1)
    DRAFT --> PENDING_REVIEW : re-analysis finished
    APPROVED --> [*]
    REJECTED --> [*]

    note right of DRAFT
        Revision limit: CAREERCREW_MAX_REVISIONS
        (default 2). A third request is refused.
    end note
```

```mermaid
flowchart TB
    subgraph TABS["The four tabs"]
        T1["1 · Analyze match<br/>always available"]
        T3["3 · Mock interview"]
        T2["2 · Prep coach"]
        T4["4 · Post-interview coach"]
    end

    T1 --> CHECK{"_is_approved(ctx_state)?"}
    T2 --> CHECK
    T3 --> CHECK
    T4 --> CHECK

    CHECK -- "status is APPROVED" --> OK["Run normally"]
    CHECK -- "DRAFT / PENDING_REVIEW / REJECTED" --> NO["Refuse with a message:<br/>approve the bundle first"]

    OK --> USE["Read the persisted context:<br/>profile, requirements, gaps,<br/>prep plan, transcript"]
```

The transition table is code, not convention:

```27:36:careercrew/review.py
_ALLOWED: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.DRAFT: {ReviewStatus.PENDING_REVIEW},
    ReviewStatus.PENDING_REVIEW: {
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.DRAFT,  # a requested revision returns to a fresh draft
    },
    ReviewStatus.APPROVED: set(),
    ReviewStatus.REJECTED: set(),
}
```

**What to notice**

- **The analysis results stay readable while pending.** Only the three practice
  tabs are gated; the match report and prep plan are visible, because the
  candidate needs them in order to decide.
- **Revision is bounded and requires feedback.** `apply_decision` raises if the
  notes are empty or the count would exceed the limit
  (`careercrew/review.py:118-127`).
- **The gate reads the database, not the browser.** `_is_approved` reads the
  persisted `packages.status`, so refreshing the page or opening a second tab
  cannot bypass the review (`careercrew/callbacks_interview.py:30-44`).

---

## 6. Guardrails — every check, where it runs, and what it costs

Guardrails are plain functions returning a list of problem strings. There are
two severities: **fail closed** (raise, show nothing) and **warn** (continue,
show a banner).

```mermaid
flowchart TB
    subgraph IN["Input path — before any model call"]
        I1["check_upload(name)<br/>extension + 5 MB"]
        I2["redact_pii(text)<br/>emails, phones"]
        I3["validate_request(...)<br/>exactly one source each,<br/>size, not a URL,<br/>_DISALLOWED_INPUT"]
    end

    subgraph TOOL["Tool path — inside document_tools"]
        TL1["_safe_upload_path<br/>upload-folder confinement"]
        TL2["redact_pii on the extracted text"]
    end

    subgraph OUT["Output path — after the model answers"]
        O1["validate_citations<br/>each bullet cites a real fact"]
        O2["validate_package<br/>required fields + citations"]
        O3["validate_prep_plan<br/>focus areas cite real gaps,<br/>priorities valid, shares ≈100"]
        O4["validate_interview_answer<br/>answer size + injection"]
        O5["validate_evaluation<br/>score 0-100, fields bounded"]
        O6["validate_transcript_turn<br/>turn role and text"]
        O7["validate_coaching_reply<br/>reply size, no invented facts"]
    end

    I1 --> FAIL["FAIL CLOSED<br/>raise → nothing rendered"]
    I3 --> FAIL
    O2 --> FAIL
    O1 --> FAIL

    O3 --> WARN["WARN<br/>bundle rendered + banner"]
    O4 --> WARN
    O5 --> WARN
    O6 --> WARN
    O7 --> WARN

    IN --> TOOL --> OUT
```

| Check | File and lines | Severity | Why that severity |
|---|---|---|---|
| `check_upload` | `careercrew/guardrails.py:46-54` | fail closed | Accepting an unreadable type wastes a full run. |
| `redact_pii` | `careercrew/guardrails.py:39-43` | transform | Removes emails and phones before any model sees the text. |
| `validate_request` | `careercrew/guardrails.py:65-115` | fail closed | Two sources or a URL means the run is ambiguous. |
| `_safe_upload_path` | `careercrew/document_tools.py:41-56` | fail closed | Blocks `../` escapes out of `uploads/`. |
| `validate_citations` | `careercrew/guardrails.py:130-152` | fail closed via `validate_package` | An uncited bullet is an invented claim. |
| `validate_package` | `careercrew/guardrails.py:271-295` | fail closed | The last gate before the bundle is displayed. |
| `validate_prep_plan` | `careercrew/guardrails.py:155-193` | warn | Advice can be imperfect without being dishonest. |
| `validate_interview_answer` | `careercrew/guardrails.py:196-211` | warn | Re-asks for a real answer. |
| `validate_evaluation` | `careercrew/guardrails.py:214-231` | warn | Keeps a bounded score. |
| `validate_transcript_turn` | `careercrew/guardrails.py:234-244` | warn | Keeps the transcript well-formed. |
| `validate_coaching_reply` | `careercrew/guardrails.py:247-268` | warn | Replaces a bad reply rather than crashing the chat. |

**What to notice**

- **The severity choice is the design.** Anything that fabricates evidence
  fails closed; anything that only degrades quality warns and renders.
- **`validate_citations` is enforced through `validate_package`**, which is why
  a citation problem produces a hard failure in the pipeline.
- **Guardrails never call a model.** They are deterministic functions of the
  strings and models passed in, so they are fully unit tested offline.

---

## 7. Two execution modes

The same entry points run with or without a key. The difference is which
branches exist, and the UI says which one you got.

```mermaid
flowchart TB
    START["Analyze match"] --> KEY{"settings.has_llm<br/>(OPENAI_API_KEY set?)"}

    KEY -- yes --> TRY["Run the five-agent crew"]
    TRY --> OK{"kickoff succeeded?"}
    OK -- yes --> FULL["Full result:<br/>profile · requirements · gaps<br/>· feedback · LLM prep plan"]
    OK -- "no (exception caught)" --> FB

    KEY -- no --> FB["Deterministic fallback"]

    FB --> FBP["build_fallback_plan()<br/>seniority band + question themes"]
    FB --> FBW["warnings + 'limited mode' banner<br/>match report stays empty"]

    FULL --> VAL["validate_package → validate_prep_plan"]
    FBP --> VAL
    FBW --> VAL
    VAL --> RESULT["PipelineResult(used_fallback=…)"]
```

**What to notice**

- **A crew exception is caught, not raised.** The user still gets a bundle, plus
  a warning (`careercrew/pipeline.py:395-399`).
- **The offline path has no gaps to plan from**, so the prep plan carries only
  the seniority band and question themes. That is why the match report is
  empty — there was no analysis, and the app does not pretend otherwise.
- **`used_fallback` travels in the result**, so the callback can label the run
  instead of silently presenting fallback output as agent output.

---

## 8. Persistence model

Five tables. `packages` is the center of gravity; everything else points at it.

```mermaid
erDiagram
    packages ||--o{ decisions : "review history"
    packages ||--o{ interview_sessions : "practice sessions"

    interview_sessions ||--o{ interview_turns : "transcript"
    interview_sessions ||--o{ chat_messages : "coach messages"

    packages {
        TEXT package_id PK
        TEXT role_title
        TEXT company
        TEXT inputs_json
        TEXT package_json
        TEXT trace_json
        TEXT status
        INTEGER revision_count
        TEXT created_at
        TEXT updated_at
    }
    decisions {
        INTEGER id PK
        TEXT package_id FK
        TEXT decision
        TEXT feedback
        TEXT decided_at
    }
    interview_sessions {
        TEXT session_id PK
        TEXT package_id FK
        TEXT role_title
        TEXT session_json
        INTEGER overall_score
        INTEGER completed
    }
    interview_turns {
        INTEGER id PK
        TEXT session_id FK
        INTEGER question_index
        TEXT role
        TEXT text
    }
    chat_messages {
        INTEGER id PK
        TEXT session_id FK
        TEXT channel
        TEXT role
        TEXT content
    }
```

**What to notice**

- **The status column is the approval gate.** Tables 2-4 exist to make a
  practice session and its coaching history survive a page refresh.
- **The schema lives in one string.** `SCHEMA` is executed with
  `CREATE TABLE IF NOT EXISTS`, so there is no migration step to run
  (`careercrew/session_store.py:21-73`).
- **`chat_messages` is append-only.** Chat history is written for auditability;
  the live conversation is held in the Gradio component.

---

## 9. Progress reporting — how a stage lights up

The tracker has six steps. A CrewAI task callback maps an agent name onto a
step number, and the runner converts that into a yielded tuple.

```mermaid
flowchart LR
    subgraph WORKER["Worker thread"]
        T1["task_callback(TaskOutput)"] --> MAP["AGENT_STAGE / TASK_STAGE<br/>agent name → Stage"]
        MAP --> DICT["stages['index'] = stage + 1"]
    end

    subgraph EVENT["Gradio event thread"]
        POLL["while not future.done()"] --> YIELD["yield (target, detail)"]
        YIELD --> RENDER["_stages_html(target, detail)"]
        POLL --> WAIT["wait_futures([future], 1.0)"]
        WAIT --> POLL
    end

    DICT -.shared dict.-> POLL
    FUT["pool.submit(run_analysis, …)<br/>max_workers=1"] --> WORKER
```

The step names, quoted:

```30:38:careercrew/runner.py
STAGES: list[tuple[int, str, str]] = [
    (Stage.CHECK, "Check inputs", "Make sure your resume and job posting look valid"),
    (Stage.RESUME, "Read resume", "Pull out skills, roles, and achievements from your resume"),
    (Stage.ROLE, "Understand role", "Extract what the job actually requires"),
    (Stage.MATCH, "Score match", "Mark each requirement as covered, reframeable, or out of scope"),
    (Stage.REWRITES, "Draft rewrites", "Suggest stronger bullets backed by facts from your resume"),
    (Stage.PREP, "Prep plan", "Plan where to spend your interview preparation time"),
]
```

**What to notice**

- **One worker, deliberately.** `max_workers=1` serializes runs so two clicks
  cannot interleave crew state.
- **The worker writes, the event thread reads.** A plain dict is the mailbox;
  the poll loop wakes every second.
- **The number and the enum are the same thing**, so the UI never passes a bare
  `6` to mean "prep plan" (`careercrew/runner.py:18-26`).

---

## 10. Request-changes loop — what a revision actually re-runs

"Request changes" is not an edit. It returns the package to `DRAFT`, folds the
candidate's notes into the experience, and runs the whole pipeline again.

```mermaid
sequenceDiagram
    autonumber
    actor U as Candidate
    participant CB as callbacks_analyze.request_revision
    participant RV as review.apply_decision
    participant DB as session_store
    participant P as pipeline.run_analysis
    participant G as guardrails

    U->>CB: type notes, press "Apply updates & re-analyze"
    CB->>CB: load the previous context from ctx_state
    CB->>RV: apply_decision(REVISE, feedback=notes)
    RV->>RV: require non-empty notes
    RV->>RV: check revision_count + 1 ≤ max_revisions
    RV->>DB: record_decision, status → DRAFT
    RV-->>CB: ReviewOutcome(needs_revision=True)

    CB->>P: run_analysis(request with revision_notes)
    P->>P: normalize inputs, validate_request
    P->>P: crew.kickoff(inputs=crew_inputs(revision_notes=…))
    Note over P: _apply_revision_experience merges<br/>attested experience into profile/gaps
    P->>G: validate_package → validate_prep_plan
    P-->>CB: a new PipelineResult

    CB->>DB: submit_for_review → PENDING_REVIEW
    CB-->>U: fresh report, prep plan, and a new revision_count
```

**What to notice**

- **The previous bundle is reused, not discarded.** The callback reloads
  `ctx_state` first, so the notes are applied to the analysis already on screen.
- **The revision limit is enforced before any work starts.** A third request is
  refused with a message rather than burning a full run
  (`careercrew/review.py:118-127`).
- **The candidate's own words are treated as evidence.** This is the one place
  where a human assertion enters the profile — flagged in the warnings
  (`careercrew/pipeline.py:418-434`).

---

## 11. Where to go next

| Question | Document |
|---|---|
| What does pressing Analyze do, line by line? | `docs/ANALYZE_BUTTON_WALKTHROUGH.md` |
| What is the responsibility of one specific module? | `docs/code-walkthrough/INDEX.md` |
| Why was it built this way? | `ARCHITECTURE.md` §4 |
| What are the requirements and their evidence? | `docs/engineering/functional-nonfunctional-requirements.md` |
| How do I run and test it? | `docs/engineering/setup.md`, `docs/engineering/testing-and-release.md` |
