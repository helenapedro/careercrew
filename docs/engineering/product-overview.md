## 1. Product Abstract

**CareerCrew: Evidence-Grounded AI Career Preparation**

CareerCrew is an AI-powered career preparation platform that helps job seekers tailor their application materials and prepare for interviews based on their actual experience and a target job description.

Users provide a resume and a job description; seniority is inferred from the JD. CareerCrew analyzes the candidate profile against role requirements, identifies strengths and gaps, generates evidence-supported resume feedback and talking points, and develops a personalized interview-preparation plan. On top of that workflow it supports voice or text mock interviews and contextual coaching.

The system is intended to coordinate a sequential multi-agent workflow, structured data models, document tools, and output validation, with human review before users rely on generated material. Recommendations should be grounded in verifiable candidate information; unsupported claims should be flagged rather than invented. CareerCrew assists with preparation and practice and does not submit job applications on the user's behalf.

### Intended user groups

1. **Job seekers applying for professional roles** — the primary user group. They need to understand their fit for a target role and prepare credible application materials and interview answers.
2. **Students and early-career professionals** — users who may need more structured guidance with resume presentation, interview practice, and professional communication.
3. **Career advisors and university career services** — a potential institutional user group that could use CareerCrew to support multiple job seekers. This group is an intended/potential audience, but should not be described as an already validated customer segment unless further evidence supports that claim.

These groups have different needs: individual job seekers want help with a specific opportunity; students and early-career professionals may need more guided practice; career advisors and career services may need ways to support multiple people consistently.

**Product aim:** Make job preparation more focused, consistent, transparent, and aligned with the target role while keeping candidate claims evidence-grounded.

## 2. Product Scope and Boundaries

### In scope

- Resume and job-description analysis.
- Candidate-profile and job-requirement extraction.
- Evidence-based assessment of strengths, gaps, and requirement coverage.
- Tailored resume feedback and talking points.
- Interview-preparation plans based on the role and identified gaps.
- Mock interview practice and feedback through supported text and/or voice workflows.
- Preparation and post-interview coaching where implemented.
- Review, validation, and persistence of preparation artifacts where implemented.

### Out of scope

- Submitting applications to employers on the user's behalf.
- Inventing candidate experience, qualifications, employment history, work authorization, or other personal facts.
- Treating generated output as verified without validation and user review.
- Claiming production reliability, efficacy, adoption, or product-market fit without supporting evidence.

### Scope notes

- Resume, job-description, and interview workflows must be checked against the current `dev` implementation.
- URL ingestion, specific file formats, voice features, persistence behavior, and tool fallbacks should be documented as supported only after code and tests confirm them.
- Career advisors and university career services are included as a potential institutional audience; their needs and willingness to adopt the product still require validation.


## 3. Product Goals and Proposed Success Measures

These are proposed goals. Quantitative targets should be set after a baseline is measured.

| ID | Goal | Candidate measure |
|---|---|---|
| G-01 | Improve job-specific preparation | Percentage of valid resume/job-description inputs that produce a complete, usable preparation package |
| G-02 | Keep recommendations evidence-grounded | Percentage of factual recommendations with traceable supporting evidence; number of unsupported claims reaching the final output |
| G-03 | Focus preparation on relevant gaps | Percentage of preparation plans that address identified role-specific gaps and the selected experience level |
| G-04 | Support interview practice | Percentage of completed mock interviews that produce actionable feedback and a final evaluation, where supported |
| G-05 | Provide continuity | Successful retrieval rate for saved preparation and practice history, where persistence is implemented |
| G-06 | Handle failures safely | Percentage of invalid inputs and dependency failures handled without silently treating invalid output as success |
## 4. Key Features

1. **Resume and job-description ingestion** — accept supported document uploads or pasted text; URL ingestion should be listed only if verified.
2. **Candidate and role analysis** — extract candidate facts and job requirements into structured representations.
3. **Evidence-based fit and gap analysis** — classify requirement coverage, highlight strengths and gaps, and provide supporting evidence.
4. **Application-preparation package** — provide tailored resume feedback, talking points, and a prioritized preparation plan.
5. **Mock interview and evaluation** — generate role-relevant practice questions and provide feedback through supported text and/or voice workflows.
6. **Contextual coaching** — support preparation and post-interview reflection where implemented.
7. **Review and trust controls** — validate outputs, flag unsupported claims, and let the user approve, revise, or reject suggestions.
8. **Persistence and continuity** — store and retrieve relevant preparation artifacts and practice history where implemented.
9. **Failure handling and fallbacks** — provide understandable status and errors, with bounded retries and documented fallbacks.

