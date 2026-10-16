## 3. Use Cases

These diagrams present the intended use cases at a glance. They are **product-level drafts**; confirm which actions are implemented in `dev` before treating them as verified functionality.

### 3.1 Use-case overview by user group

```mermaid
flowchart TB
    subgraph IND["Individual users — core intended audience"]
        direction LR
        JS["Job seeker"]
        EC["Student / early-career professional"]
    end

    subgraph SELF["CareerCrew workflows for individuals"]
        direction LR
        U1(["1. Analyze resume + job description"])
        U2(["2. Identify strengths + gaps"])
        U3(["3. Generate resume feedback"])
        U4(["4. Prepare screening answers"])
        U5(["5. Build interview prep plan"])
        U6(["6. Practice mock interview"])
        U7(["7. Review interview feedback"])
        U8(["8. Continue coaching"])
        U1 --> U2 --> U3
        U2 --> U4
        U2 --> U5 --> U6 --> U7 --> U8
    end

    JS --> U1
    JS --> U4
    EC --> U1
    EC --> U5
    EC --> U6

    subgraph INST["Potential institutional audience — not yet verified"]
        direction LR
        CA["Career advisor / university career services"]
        U9(["Potential: support multiple job seekers"])
        CA -.-> U9
        U9 -. "would require validated multi-user support" .-> U1
    end

    classDef jobseeker fill:#DCEBFF,stroke:#2563EB,color:#172554,stroke-width:2px;
    classDef earlycareer fill:#DDF7E8,stroke:#15803D,color:#14532D,stroke-width:2px;
    classDef workflow fill:#F3F4F6,stroke:#6B7280,color:#111827;
    classDef future fill:#FFF0D6,stroke:#C2410C,color:#7C2D12,stroke-dasharray: 5 5;

    class JS jobseeker;
    class EC earlycareer;
    class U1,U2,U3,U4,U5,U6,U7,U8 workflow;
    class CA,U9 future;
    style IND fill:#F8FAFC,stroke:#64748B,stroke-width:1px
    style SELF fill:#F9FAFB,stroke:#9CA3AF,stroke-width:1px
    style INST fill:#FFFBEB,stroke:#D97706,stroke-dasharray: 5 5
```

**How to read this diagram**
- **Blue:** job seekers.
- **Green:** students and early-career professionals.
- **Grey:** individual CareerCrew workflows that these users can access; the arrows indicate example entry points, not exclusive permissions.
- **Orange dashed:** the potential career-advisor/institutional use case, which is not confirmed as implemented.

> **Audience note:** The job seeker and student/early-career workflows align with the individual-preparation concept. Career advisors and university career services are a potential institutional audience; multi-user or advisor-specific functionality needs validation before it is presented as an existing feature.

### 3.2 UC-01 — Prepare for a target job

```mermaid
flowchart TD
    A([Start]) --> B["1. Provide resume"]
    B --> C["2. Provide target job description"]
    C --> D{"3. Inputs valid?"}
    D -- No --> E["Correct inputs and retry"]
    E --> B
    D -- Yes --> F["4. Extract candidate profile"]
    F --> G["5. Analyze job requirements"]
    G --> H["6. Compare evidence with requirements"]
    H --> I["7. Identify strengths and gaps"]
    I --> J["8. Generate tailored feedback and prep plan"]
    J --> K["9. Validate output and evidence"]
    K --> L{"10. Output valid?"}
    L -- No --> M["Retry or show failure / fallback"]
    M --> Z([End without claiming success])
    L -- Yes --> N["11. User reviews suggestions"]
    N --> O{"12. User decision"}
    O -- Revise --> J
    O -- Reject --> P([End without approval])
    O -- Approve --> Q["13. Use preparation package"]
    Q --> R["14. Optional: screening prep or mock interview"]
    R --> S([End])
```

**Actor:** Job seeker  
**Outcome:** A reviewed preparation package grounded in the user's supplied experience, when the workflow succeeds.  
**Boundary:** CareerCrew prepares the user; it does not submit an application.

### 3.3 UC-02 — Prepare employer screening answers

```mermaid
flowchart TD
    A([Start]) --> B["1. Provide screening questions"]
    B --> C["2. Load verified candidate information"]
    C --> D["3. Match each question to available evidence"]
    D --> E{"4. Evidence sufficient?"}
    E -- Yes --> F["5. Draft supported answer"]
    E -- No --> G["5. Flag question for user input"]
    F --> H["6. Validate for unsupported claims"]
    G --> I["6. User supplies or confirms missing information"]
    I --> H
    H --> J["7. User reviews answer"]
    J --> K{"8. Accept answer?"}
    K -- No --> L["Revise or discard"]
    K -- Yes --> M["9. Copy/use answer outside CareerCrew"]
    L --> J
    M --> N([End])
```

**Actor:** Job seeker  
**Outcome:** Screening-answer drafts the user can review and use.  
**Guardrail:** Never invent personal facts or submit answers to an employer.

### 3.4 UC-03 — Practice for an interview

```mermaid
flowchart TD
    A([Start]) --> B["1. Select target role / preparation context"]
    B --> C["2. Generate role-relevant question"]
    C --> D["3. Answer by supported text or voice"]
    D --> E["4. Evaluate answer"]
    E --> F["5. Provide feedback and improvement suggestions"]
    F --> G{"6. Continue practice?"}
    G -- Yes --> C
    G -- No --> H["7. Summarize session, if supported"]
    H --> I["8. Save or retrieve session, if configured"]
    I --> J([End])
```

**Actor:** Job seeker or student/early-career professional  
**Outcome:** Practice and actionable feedback where the relevant interview workflow is implemented.  
**Implementation check:** Confirm voice support, evaluation format, session summaries, and persistence in `dev`.

### 3.5 UC-04 — Career advisor supports job seekers (potential use case)

```mermaid
flowchart TD
    A(["Start — potential future workflow"]) --> B["1. Advisor identifies a job seeker's preparation need"]
    B --> C["2. Job seeker provides resume and target role"]
    C --> D["3. CareerCrew generates preparation materials"]
    D --> E["4. Job seeker reviews materials and practices"]
    E --> F["5. Advisor provides additional guidance"]
    F --> G["6. Job seeker revises preparation"]
    G --> H(["End"])

    classDef future fill:#FFF0D6,stroke:#C2410C,color:#7C2D12,stroke-dasharray: 5 5;
    class A,B,C,D,E,F,G,H future;
```

**Actor:** Career advisor or university career-services staff  
**Status:** This diagram captures a possible future workflow, **not a claim that advisor accounts, multi-user management, or advisor dashboards currently exist**. Validate this audience and its needs before adding it to the implemented feature set.

### 3.6 Use-case relationships at a glance

```mermaid
flowchart TB
    INPUT["Resume + job description"] --> ANALYSIS["Job-fit and gap analysis"]
    ANALYSIS --> PACKAGE["Preparation package"]
    PACKAGE --> RESUME["Resume feedback"]
    PACKAGE --> SCREEN["Screening-answer preparation"]
    PACKAGE --> PLAN["Interview preparation plan"]
    PLAN --> MOCK["Mock interview"]
    MOCK --> FEEDBACK["Interview feedback"]
    FEEDBACK --> COACH["Follow-up coaching, if implemented"]
    COACH -. "May inform another practice cycle" .-> MOCK
```

### Use-case verification checklist

- [ ] Confirm resume and job-description input methods and file formats.
- [ ] Confirm the actual analysis steps and output schemas.
- [ ] Confirm whether users can approve, revise, or reject suggestions in the current UI.
- [ ] Confirm screening-answer preparation and its evidence guardrails.
- [ ] Confirm text and voice mock-interview paths and evaluation outputs.
- [ ] Confirm coaching and session-history persistence.
- [ ] Treat advisor/multi-user support as future scope unless code proves otherwise.

## 4. User Stories and Acceptance Criteria

The user stories below are grouped by the user outcome. Each story uses the familiar format **As a [user], I want [capability], so that [benefit]**. Acceptance criteria describe how the story can be verified; they are proposed until checked against the implementation.

### User story map

```mermaid
flowchart TB
    GOAL["CareerCrew helps people prepare for a target job"]
    GOAL --> A["Understand job fit"]
    GOAL --> B["Prepare application materials"]
    GOAL --> C["Practice interviews"]
    GOAL --> D["Continue improving"]

    A --> A1["US-01: Analyze job fit"]
    B --> B1["US-02: Improve resume honestly"]
    B --> B2["US-03: Prepare screening answers"]
    C --> C1["US-04: Practice interviews"]
    D --> D1["US-05: Continue coaching"]

    classDef goal fill:#1F2937,stroke:#111827,color:#FFFFFF,stroke-width:2px;
    classDef outcome fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,stroke-width:1.5px;
    classDef story fill:#F3F4F6,stroke:#6B7280,color:#111827;
    class GOAL goal;
    class A,B,C,D outcome;
    class A1,B1,B2,C1,D1 story;
```

### US-01 — Analyze job fit

<box>
**As a** job seeker, **I want** to compare my resume with a job description, **so that** I can understand my strengths and gaps for the role.

**Acceptance criteria**
- [ ] The system produces a structured candidate profile and job-requirements representation when inputs are valid.
- [ ] Each assessed requirement has a clear coverage classification and supporting evidence, where supported.
- [ ] Missing experience is not presented as established candidate experience.
- [ ] Invalid or incomplete inputs produce an actionable error or recovery path.
</box>

### US-02 — Improve my resume honestly

<box>
**As a** job seeker or early-career professional, **I want** tailored resume feedback and talking points, **so that** I can present relevant experience clearly without misrepresenting it.

**Acceptance criteria**
- [ ] Suggestions are tailored to the target job description.
- [ ] Factual suggestions can be traced to information supplied by the user.
- [ ] Unsupported claims are excluded or explicitly flagged.
- [ ] The user can review, revise, or reject suggestions.
</box>

### US-03 — Prepare screening answers

<box>
**As a** job seeker, **I want** help preparing answers to employer screening questions, **so that** I can respond consistently using verified information about myself.

**Acceptance criteria**
- [ ] Supported answers are drafted from a verified answer bank or other user-provided evidence.
- [ ] Questions that require unknown personal facts are flagged for user input.
- [ ] The system does not invent work authorization, notice period, location, salary, or other personal facts.
- [ ] CareerCrew does not submit the answers to the employer.
</box>

### US-04 — Practice interviews

<box>
**As a** job seeker or student/early-career professional, **I want** to practice role-specific interview questions and receive feedback, **so that** I can improve my answers before an interview.

**Acceptance criteria**
- [ ] Questions are relevant to the target role and available preparation context.
- [ ] Each answer receives actionable feedback where the evaluation workflow supports it.
- [ ] The session provides an understandable summary or evaluation when supported.
- [ ] If voice is unavailable, a supported text path remains usable where implemented.
</box>

### US-05 — Continue coaching over time

<box>
**As a** job seeker, **I want** coaching to use relevant preparation and practice history, **so that** follow-up advice builds on prior work.

**Acceptance criteria**
- [ ] Relevant prior context is available to the coaching workflow where implemented.
- [ ] The system distinguishes supplied evidence from uncertainty.
- [ ] Stored sessions can be retrieved after restart if persistence is part of the configured implementation.
- [ ] Persistence failures are surfaced rather than represented as successful saves.
</box>

### Optional institutional story — Support multiple job seekers

This is a **potential future story**, not a confirmed current capability.

**As a** career advisor or university career-services staff member, **I want** to help multiple job seekers organize their preparation, **so that** I can support them consistently.

Possible acceptance criteria to validate with intended users:
- [ ] The advisor can access only the job-seeker information they are authorized to see.
- [ ] Each job seeker's preparation materials and sessions remain separated.
- [ ] The advisor can review progress without silently changing or submitting materials on the job seeker's behalf.
- [ ] Privacy, consent, access control, and retention rules are defined before implementation.

