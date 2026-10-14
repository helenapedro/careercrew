# CareerCrew

Multi-agent resume coach built with CrewAI and MCP (CS529 Project Work 2).
Four specialized agents turn a resume and a job description into honest,
cited feedback: ATS-style coverage scoring, gap analysis, tailored bullet
rewrites, and interview talking points, with a human approving the final set.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then put your OPENAI_API_KEY in .env
```

Run the crew on the samples (fictional test data):

```bash
python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt
```

Run the web UI shell:

```bash
python app.py
```

Run the MCP server standalone (Day 4 target):

```bash
python -m mcp_server.server
```

## Layout

- `config/agents.yaml`, `config/tasks.yaml` - agent roles and task text (Day 2)
- `careercrew/models.py` - Pydantic output contracts for every task
- `careercrew/crew.py` - crew assembly: agents, tools, context, typed outputs
- `careercrew/tools.py` - CrewAI @tool wrappers (Day 2; replaced by MCP tools on Day 4)
- `careercrew/document_tools.py` - shared resume/JD logic + tool guardrails
- `careercrew/guardrails.py` - input guardrails implemented; output check stubbed (Day 3)
- `mcp_server/server.py` - FastMCP server exposing the same document tools
- `main.py` - CLI entrypoint; `app.py` - Gradio UI shell
- `samples/` - fictional resume and JD for testing

See `ARCHITECTURE.md` for the full walkthrough: data flow, each agent,
guardrails, HITL, MCP, and the Day 2/3/4 build plan.
