## 1. Proposed Functional Requirements

The following are candidate requirements for implementation review, not a claim that each one is currently satisfied.

| ID | Requirement | Status (draft) |
|---|---|---|
| FR-01 | The system shall accept a resume through at least one documented input method, such as supported upload or pasted text. | Implemented |
| FR-02 | The system shall accept a target job description through at least one documented input method. | Implemented |
| FR-03 | The system shall validate required inputs, supported file types and sizes, and conflicting input sources. | Implemented |
| FR-04 | The system shall extract a structured candidate profile and structured job requirements from valid inputs. | Implemented |
| FR-05 | The system shall compare candidate evidence with role requirements and report coverage, strengths, and gaps. | Implemented |
| FR-06 | The system shall generate tailored resume feedback and talking points grounded in candidate evidence. | Implemented |
| FR-07 | The system shall generate a preparation plan that reflects identified gaps and the target experience level. | Implemented |
| FR-08 | The system shall prepare screening answers from verified candidate information and flag unsupported questions. | Implemented |
| FR-09 | The system shall validate output structure, factual support, and required package components before presenting results as valid. | Implemented |
| FR-10 | The system shall allow the user to review, revise, approve, or reject generated suggestions. | Implemented |
| FR-11 | The system shall support role-relevant mock-interview questions and answer evaluation. | Implemented |
| FR-12 | The system shall support voice interaction when configured and provide a text alternative. | Implemented |
| FR-13 | The system shall support preparation and post-interview coaching. | Implemented |
| FR-14 | The system shall persist and retrieve preparation packages, sessions, transcripts, evaluations, and coaching history. | Implemented |
| FR-15 | The system shall expose document tools through the configured MCP integration, with a documented deterministic fallback. | Implemented |
| FR-16 | The system shall present understandable status and error messages for invalid input, failed dependencies, and unsuccessful analysis. | Partial |
| FR-17 | The system shall not submit job applications or screening answers to employers on the user's behalf. | Implemented |

## 2. Proposed Nonfunctional Requirements

| ID | Quality attribute | Proposed requirement |
|---|---|---|
| NFR-01 | Reliability | Failures must be handled predictably; invalid or incomplete output must not be silently presented as validated success. |
| NFR-02 | Performance | End-to-end latency, including model calls and retries, should be measured. Set a response-time target after establishing a baseline. |
| NFR-03 | Security | Uploaded documents and tool access must stay within approved boundaries; document tools must not permit arbitrary file access. |
| NFR-04 | Privacy | Minimize personal data, document redaction and retention behavior, and define how users can request deletion. |
| NFR-05 | AI integrity | Factual candidate claims should be traceable to supplied evidence; unsupported claims should be rejected or flagged. |
| NFR-06 | Maintainability | Keep agents, tasks, data models, orchestration, validation, and UI responsibilities modular and documented. |
| NFR-07 | Testability | Provide unit, integration, negative-path, and end-to-end tests for critical workflows. |
| NFR-08 | Portability | Supported local and deployment workflows should work with clear configuration and dependency instructions. |
| NFR-09 | Observability | Errors and outcomes should be actionable without unnecessarily logging resumes, credentials, or sensitive personal data. |
| NFR-10 | Cost control | Bound retries and measure model/tool usage per analysis and interview workflow. |
| NFR-11 | Usability and accessibility | Core workflows, validation messages, review actions, and fallbacks should be understandable and operable. |
| NFR-12 | Reproducibility | Pin or constrain dependencies, document configuration, and verify releases from a known commit. |

**Note:** These are proposed quality requirements. Privacy retention/deletion behavior, latency targets, production security, accessibility, and reliability are not established merely by an architecture description; they require implementation evidence and tests.

**Note:** Statuses are a draft assessment against the `dev` branch and must be confirmed in the verification pass proposed in `careercrew-product-draft-v0.1.md`.
