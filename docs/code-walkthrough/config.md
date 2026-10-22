# Walkthrough: `careercrew/config.py`

**File purpose:** Central env-driven settings. Secrets never hard-coded; same code for local, tests, Docker.

---

## Paths (module level)

| Constant | Points to |
|----------|-----------|
| `PROJECT_ROOT` | Repo root (`careercrew/` package’s parent) |
| `RESUME_GUIDELINES_PATH` / `INTERVIEW_GUIDELINES_PATH` | `knowledge/*.md` |
| `COACHING_GUIDELINES_PATH` | Same interview guidelines file (shared rubric) |

`load_dotenv(override=False)` — local `.env` fills gaps without overriding real env.

---

## Helpers

`_env_int` — parse integer env vars with safe defaults.

---

## `Settings` (frozen dataclass)

| Field | Env / default | Used for |
|-------|---------------|----------|
| `openai_api_key` / `openai_base_url` / `openai_model` | `OPENAI_*` | Crew + llm helper |
| `stt_model` / `tts_model` / `tts_voice` | `CAREERCREW_STT/TTS_*` | audio.py |
| `interview_question_count` | default 5 | Mock interview slider default |
| `upload_dir` / `db_path` | uploads / careercrew.db | Files + SQLite |
| `max_revisions` | default 2 | HITL revise limit |
| `app_port` | `PORT` or 7860 | Gradio |
| `log_level` | INFO | logging |

### Properties

- `has_llm` / `has_audio` — both true when an OpenAI key exists (audio reuses the same key).

---

## `get_settings()` / `reset_settings_cache()`

`@lru_cache` singleton; tests clear cache after mutating env.

**Say this:** “One Settings object; everything else reads get_settings().”
