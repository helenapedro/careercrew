# Glossary

Words used in the code talk. One idea each. The product never submits an application; it prepares and practices.

## Crew

The whole team of agents that runs when you press **Analyze match**. CareerCrew uses one crew, and the agents run one after another (sequential). There is no manager agent.

## Agent

One role in the crew, defined in `config/agents.yaml`. Each agent has a job title, a goal, and a backstory. Example: the Gap Analyst scores how well the resume covers the job.

## Task

One assignment given to one agent, defined in `config/tasks.yaml`. A task says what to read and what shape the answer must have. The five tasks run in this order: read the resume, read the job, score the gaps, draft bullet rewrites, build the prep plan.

## MCP

Model Context Protocol. A small standard way for an agent to call a tool. CareerCrew runs a local MCP server (`mcp_server/server.py`) that can read a resume file and a job-description file. The agents call those tools; they do not invent the file text.

## HITL

Human in the loop. After analysis, the prep bundle waits for a person. The buttons are **Approve**, **Reject**, and **Request changes**. Nothing is approved automatically. Request changes re-runs the analysis with the notes folded into the resume.

## Guardrail

A check that runs in code, not a hope that the model behaves. Input guardrails reject a bad file or a pasted URL. Output guardrails reject a bullet that cites a fact the resume does not contain. If an output check fails, the bundle is not shown.

## Trace

The diary of one run (`ExecutionTrace`). Each step appends an event: input accepted, a task finished, a guardrail passed or failed. It is how we explain what happened without reading model logs.

## Fallback

What still runs when there is no API key, or when the crew throws. The app does not pretend the agents ran. It builds the prep plan from the gap rules and shows a limited-mode note. With no key there is no gap report either, so that plan carries the seniority band and question themes but no focus areas.

## Stage

One step on the progress tracker, named in `careercrew/runner.py` as the `Stage` enum: check inputs, read resume, understand the role, score the match, draft rewrites, prep plan. The tracker number and the enum are the same thing, so the UI does not use a raw `6` for "prep plan".
