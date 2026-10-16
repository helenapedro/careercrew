## 10. Conceptual System Architecture

The diagram below is a **logical draft**, not a verified deployment diagram. 

```mermaid
flowchart TD
    U["Job Seeker"] --> UI["Gradio UI / CLI"]
    UI --> IG["Input Guardrails<br/>Validation, upload checks, PII redaction"]
    IG --> PL["Analysis Pipeline<br/>Normalize, orchestrate, parse, retry"]
    PL --> CREW["Sequential CrewAI Workflow"]

    subgraph AGENTS["Analysis Agents"]
        A1["1. Profile Extractor"]
        A2["2. Job Description Analyzer"]
        A3["3. Gap Analyst"]
        A4["4. Feedback Writer"]
        A5["5. Interview Prep Advisor"]
        A6["6. Screening Answer Prep Writer"]
        A1 --> A2 --> A3 --> A4 --> A5 --> A6
    end

    CREW --> AGENTS
    A1 -.-> MCP["MCP Tool Server"]
    A2 -.-> MCP
    A6 -.-> MCP
    MCP --> DT["Document Tools<br/>Resume, JD, verified answer bank"]

    AGENTS --> OG["Output Validation<br/>Evidence, schemas, plan, package"]
    OG --> HITL{"Human Review"}
    HITL -->|Approve| PKG["Approved Preparation Package"]
    HITL -->|Revise| PL
    HITL -->|Reject| STOP["Stop without approval"]

    PKG --> MI["Mock Interview<br/>Voice / Text, Transcript, Evaluation"]
    PKG --> PC["Preparation Coach"]
    MI --> POST["Post-Interview Coach"]

    IG -.-> DB[("SQLite Session Store")]
    HITL -.-> DB
    PKG -.-> DB
    MI -.-> DB
    PC -.-> DB
    POST -.-> DB

    PL <--> KB["Knowledge Files"]
    OG -.-> G["Shared Guardrails"]
    MI -.-> G
    PC -.-> G
    POST -.-> G
```

### Architecture verification checklist

- [ ] Confirm the actual UI entry points and supported input methods.
- [ ] Confirm the exact agent/task sequence and data contracts.
- [ ] Confirm whether MCP tools and deterministic fallbacks are both implemented.
- [ ] Confirm how output validation, retries, and package completeness are enforced.
- [ ] Confirm whether human approval/revision/rejection exists in the UI or is only a proposed interaction.
- [ ] Confirm which workflows use SQLite or other persistence and what is stored.
- [ ] Confirm the actual mock-interview, voice/text, and coaching paths.
- [ ] Update the diagram to distinguish in-process modules from external services.
