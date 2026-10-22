# Deploy CareerCrew to Hugging Face Spaces

> A Docker Space needs a paid Hugging Face plan before the free CPU Basic
> machine can be created. Any plain Docker host avoids that requirement; the
> image below is the same one you would run there.

CareerCrew is a Gradio app (`app.py`) that already listens on `0.0.0.0:7860`.
The `Dockerfile` in the repo root is written for a **Docker Space**: it installs
`requirements.txt`, starts `python app.py`, and keeps SQLite and uploads under
`/data`.

Checked against the Hugging Face docs on 2026-10-21:
[Spaces overview](https://huggingface.co/docs/hub/spaces-overview),
[Manage your Space](https://huggingface.co/docs/huggingface_hub/guides/manage-spaces),
[pricing](https://huggingface.co/pricing).

---

## Is it free?

The **machine** this app needs is free. **Creating the Space is not free** on a
personal account with no subscription.

| What | Cost |
|------|------|
| CPU Basic hardware (2 vCPU, 16 GB RAM) | **$0 per hour.** Leave the Space on this. Do not pick a GPU. |
| Creating a Docker or Gradio Space | Requires a **paid Hugging Face plan**: PRO for a personal account, Team or Enterprise for an organization. A free account gets an HTTP 402 if it tries to create one. See the current monthly price on [huggingface.co/pricing](https://huggingface.co/pricing). |
| ZeroGPU Gradio Spaces | Free accounts can host up to 2 of these. **CareerCrew cannot use ZeroGPU.** It is a CPU app that calls OpenAI. It is not a model loaded on a Hugging Face GPU. |
| OpenAI (`OPENAI_API_KEY`) | Billed by **OpenAI**, not by Hugging Face, per token. With no key the page still opens in limited mode (seniority band and themes only; the five-agent crew does not run, so there is no match report and no gap-driven focus areas). |
| Disk (`/data/careercrew.db` and uploads) | **Ephemeral** on the free disk (50 GB, wiped on restart, rebuild, or sleep). A Storage Bucket that survives restarts is **paid**. |
| Idle time | On CPU Basic the Space **sleeps** when nobody uses it. The next visit waits for it to wake up. Staying awake all the time means paid hardware. |

For a class demo, the usual setup is: Hugging Face PRO (or an org plan) so you
can create the Space, CPU Basic so the hardware stays $0/hour, and your own
OpenAI key for the live crew. Do not upgrade the Space to a GPU.

A **public** Space lets anyone who opens the URL spend your OpenAI key. Use a
**private** Space when the key is a real paid key, or watch the OpenAI usage
dashboard during the demo.

---

## What the container already does

`Dockerfile`:

- Base image `python:3.12-slim` (the project requires Python `>=3.11,<3.13`).
- `PORT=7860`, which is the port Spaces expects.
- `CAREERCREW_DB_PATH=/data/careercrew.db` and `CAREERCREW_UPLOAD_DIR=/data/uploads`.
- Runs as non-root `appuser`.
- `CMD ["python", "app.py"]`. `app.py` calls `launch(server_name="0.0.0.0", server_port=...)`.
- The MCP server is started by the app over stdio. There is no second process to deploy.

The image copies `samples/`, so **Try a sample resume** and **Try a sample job** work inside the container.

---

## 1. Create the Space

1. Sign in at [huggingface.co](https://huggingface.co). The account needs a plan that can create Docker Spaces (see the cost table above).
2. Open [huggingface.co/new-space](https://huggingface.co/new-space).
3. Set:
   - **SDK:** Docker
   - **Hardware:** CPU Basic
   - **Visibility:** Private if the OpenAI key must not be shared. Public if the demo link has to work without a Hugging Face login.
4. Create the Space. Hugging Face gives you an empty Git repo, for example `https://huggingface.co/spaces/<user>/careercrew`.

---

## 2. Put the project in that repo

From the CareerCrew project root (`Project2/careercrew`), add the Space as a second remote. Do not replace `origin` (that remote is GitHub).

```bash
git remote add space https://huggingface.co/spaces/<user>/careercrew
git push space dev:main
```

Spaces builds the branch named `main` inside the Space repo. `dev:main` publishes your `dev` branch there without renaming it on GitHub.

If `git push` asks for a password, use a Hugging Face **access token** with write permission (Settings → Access Tokens), not your Hugging Face password. The username is your Hugging Face username.

Do **not** push a `.env` file. The key goes in Space secrets in the next step.

---

## 3. Set the secret

In the Space: **Settings → Secrets and variables → New secret**.

| Name | Value |
|------|--------|
| `OPENAI_API_KEY` | your OpenAI key (`sk-...`) |

Optional variables, only if you want to override the defaults in `.env.example`:

| Name | Default in code |
|------|-----------------|
| `OPENAI_MODEL` | `gpt-6-luna` |
| `CAREERCREW_STT_MODEL` | `whisper-1` |
| `CAREERCREW_TTS_MODEL` | `tts-1` |
| `CAREERCREW_TTS_VOICE` | `alloy` |
| `CAREERCREW_INTERVIEW_QUESTIONS` | `5` |
| `CAREERCREW_MAX_REVISIONS` | `2` |

Leave `CAREERCREW_DB_PATH` and `CAREERCREW_UPLOAD_DIR` unset. The Dockerfile already points them at `/data`.

Save the secret, then **Factory reboot** the Space (Settings) so the running container picks it up.

---

## 4. Wait for the build

Open the Space **Logs** tab.

- A healthy build ends with the container listening on port 7860.
- The public URL is `https://huggingface.co/spaces/<user>/careercrew` (the app itself is also served at `https://<user>-careercrew.hf.space`).

First boot installs CrewAI and the rest of `requirements.txt`, so the build can take several minutes.

---

## 5. Check the demo

1. Open the Space URL.
2. The top bar says **Ready** when `OPENAI_API_KEY` is set, and **Limited mode** when it is not.
3. Paste a resume and a job description, or use the sample buttons.
4. Press **Analyze match**. The five-agent run calls OpenAI, so it takes the same time as it does locally.
5. Open **Mock interview** only if you want speech. Whisper and TTS also use the same OpenAI key.

---

## What does not survive a restart

CPU Basic disk is wiped when the Space sleeps, rebuilds, or is factory-rebooted.

Lost on restart:

- `careercrew.db` (approved bundles, review history, interview sessions, coach chats)
- files in `/data/uploads`

Kept:

- the code you pushed
- Space secrets, including `OPENAI_API_KEY`

That matches a live demo. It does not match a long-lived product. Durable storage means a paid Storage Bucket mounted at `/data`. Do not put resumes in a **public** bucket: those files are reachable by URL.

---

## Update an existing Space

```bash
git push space dev:main
```

The Space rebuilds from the new commit. Secrets stay in place.

---

## If the build fails

| Log symptom | What to change |
|-------------|----------------|
| App exits immediately, or "port" errors | `app.py` must keep `server_name="0.0.0.0"` and `server_port` from `PORT` (already the case). |
| `ModuleNotFoundError` | The missing package must be in `requirements.txt`. The image installs that file, not `pyproject.toml` optional extras. |
| Sample buttons say the file is missing | Confirm `COPY samples ./samples` is still in the Dockerfile, then rebuild. |
| Page opens in **Limited mode** | `OPENAI_API_KEY` is missing or the Space was not rebooted after the secret was saved. |
| Build runs out of memory | Stay on CPU Basic (16 GB). Do not switch to a GPU for this app. |
| HTTP 402 when creating the Space | The account cannot create Docker Spaces yet. That is the plan limit in the cost table, not a bug in this repo. |
