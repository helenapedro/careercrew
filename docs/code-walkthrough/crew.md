# Walkthrough: `careercrew/crew.py`

**File purpose:** Turns YAML roles/tasks into a **sequential** CrewAI crew of five agents, wires MCP + knowledge, and builds kickoff inputs. No manager agent.

**Flow doc:** [CODE_PATH_ANALYZE.md](../CODE_PATH_ANALYZE.md) §4

---

## Imports

| Import | Why |
|--------|-----|
| `yaml` | Load `config/agents.yaml` and `tasks.yaml` |
| `Agent`, `Crew`, `LLM`, `Process`, `Task` | CrewAI primitives |
| `StringKnowledgeSource` | Inject guideline markdown as agent knowledge |
| `crewai_mcp_server` | Attach real MCP stdio server to tool-using agents |
| Output models | `output_pydantic=` so each task returns a typed object |

---

## Module paths

- `CONFIG_DIR` = project `config/` (parent of `careercrew/` package)  
- `AGENTS_YAML`, `TASKS_YAML` — roles vs task text only; wiring is here  

---

## Functions

### `_load_yaml(path)`

**What:** Open UTF-8, `yaml.safe_load`.  
**Why:** Keep agent/task prose editable without touching Python.

### `_guidelines_source(path, name)`

**What:** Read file contents into `StringKnowledgeSource` with metadata.  
**Why:** Passing **content** (not a relative path) avoids CrewAI working-directory knowledge bugs.  
**I/O:** Read `knowledge/*.md`.

### `build_crew(*, verbose, on_task, on_step)` — **core**

**What:**

1. Push `OPENAI_API_KEY` / `OPENAI_BASE_URL` into env if set in settings  
2. Load YAML configs  
3. Create one MCP server config + resume knowledge + interview knowledge  
4. Nested `_agent(name, with_mcp, extra_knowledge)`:
   - Always resume guidelines; optional interview guidelines  
   - `allow_delegation=False` (no peer handoff)  
   - If `with_mcp`: attach MCP server  
5. Instantiate five agents (MCP on: profile and JD; off: gap, feedback, prep)  
6. Instantiate five tasks with `output_pydantic` and `context=[...]` dependencies  
7. Return `Crew(..., process=Process.sequential, memory=False, task_callback=on_task)`

**Agent ↔ MCP map:**

| Agent | MCP? | Extra knowledge |
|-------|------|-----------------|
| Profile Extractor | Yes | resume |
| JD Analyzer | Yes | resume |
| Gap Analyst | No | resume |
| Feedback Writer | No | resume |
| Interview Prep Advisor | No | resume + interview |

**Task context edges:**

- gaps ← profile + JD  
- feedback ← gaps  
- prep plan ← profile + JD + gaps  

**Why sequential / no manager:** Pipeline is linear; a manager adds latency/cost with no branching decision.  
**Why memory=False:** Each task already receives the previous task's output through `context`. CrewAI memory would add another model call after every agent.  
**Why an explicit `llm=` on every agent:** Without it CrewAI silently uses its own built-in default model, and `OPENAI_MODEL` only affected the coach/interview helper. Building one `LLM(model=settings.openai_model, ...)` and passing it to all five agents makes the configured model govern the whole app.  
**I/O:** YAML + knowledge files; later kickoff hits OpenAI + MCP.  
**Say this:** “YAML is personality and prompts; this file is the wiring diagram.”

### `crew_inputs(...)`

**What:** Require at least one resume source and one JD source; fill kickoff dict with placeholders like `"(none; use the read_resume tool)"` when a side is unused.  
**Why:** Task templates always see `{resume_path}` / `{resume_text}` etc.; agents know which tool or paste to use.  
**Say this:** “Kickoff inputs are the variables interpolated into task descriptions.”

---

## How it connects

- **Called by:** `pipeline._run_crew`  
- **Calls:** MCP client config, YAML, knowledge files  
- **Paired with:** [config_agents_tasks.md](config_agents_tasks.md)
