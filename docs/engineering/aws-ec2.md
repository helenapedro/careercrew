# Deploy CareerCrew on AWS for the demo

One Linux server, the existing `Dockerfile`, port 7860. No GPU, no load balancer, no database service. SQLite stays on the instance disk.

This is the demo path. A Hugging Face Docker Space needs a paid Pro plan before its free CPU can be used, so Spaces is documented only as an alternative in [huggingface-spaces.md](huggingface-spaces.md).

Prices below are Linux on-demand in US East (N. Virginia), from [Amazon T3 pricing](https://aws.amazon.com/ec2/instance-types/t3/), checked 2026-10-21. Stop the instance when the demo is over. The bill runs until you stop it.

| Piece | 24 hours |
|-------|----------|
| `t3.medium` (2 vCPU, 4 GB) — use this | about **$1.00** |
| Public IPv4 address | about **$0.12** |
| 20 GB disk | a few cents |
| **Server total** | **about $1.20** |
| OpenAI, per Analyze / voice click | billed on your API key, not by AWS |

`t3.micro` (1 GB, about $0.25) and `t3.small` (2 GB, about $0.50) are too small. CrewAI runs out of memory during Analyze.

A brand-new AWS account may get 750 hours of `t3.micro` free. That free size still cannot run this app. Do not pick it to save the dollar.

---

## 1. Launch the instance

In the AWS console: **EC2 → Launch instance**.

| Setting | Value |
|---------|--------|
| Name | `careercrew-demo` |
| AMI | Ubuntu Server 24.04 LTS |
| Type | `t3.medium` |
| Key pair | Create or pick one. Download the `.pem` and keep it. |
| Storage | 20 GB gp3 |
| Security group | SSH (22) from **My IP** only. Custom TCP **7860** from **My IP** for a private demo, or from **Anywhere** (`0.0.0.0/0`) if classmates must open the link. |

Do not open port 22 to the world. Launch, then copy the **Public IPv4 address**.

---

## 2. Install Docker and copy the project

From your machine, in `Project2/careercrew`:

```bash
ssh -i /path/to/careercrew.pem ubuntu@<public-ip>
```

On the instance:

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo usermod -aG docker ubuntu
exit
```

Log in again so the `docker` group applies. From your machine, copy the project. Do not copy `.env` yet:

```bash
scp -i /path/to/careercrew.pem -r . ubuntu@<public-ip>:~/careercrew
```

Skip `.git` if the copy is slow. The image only needs the Dockerfile, `requirements.txt`, `app.py`, `main.py`, `pyproject.toml`, `README.md`, and the `careercrew`, `config`, `knowledge`, `mcp_server`, and `samples` folders.

---

## 3. Put the key on the server, not in git

On the instance:

```bash
cd ~/careercrew
cp .env.example .env
nano .env
```

Set `OPENAI_API_KEY=sk-...`. Leave the upload and database paths as they are. The container overrides them to `/data` via the Dockerfile. Save the file. `.env` is gitignored; do not commit it.

---

## 4. Build and run

Still on the instance:

```bash
docker build -t careercrew .
docker run -d --name careercrew --restart unless-stopped \
  -p 7860:7860 --env-file .env careercrew
docker logs -f careercrew
```

Wait until the log says the Gradio app is running. Then open:

```text
http://<public-ip>:7860
```

The top bar says **Ready** when the key is set, and **Limited mode** when it is not. Press **Analyze match** once. The first run is the real test: if the process is killed, the instance is out of memory and the type must stay `t3.medium` or larger.

`--restart unless-stopped` brings the app back after a reboot. It does not protect you from the hourly charge.

---

## 5. Stop paying

When the demo is finished:

```bash
docker stop careercrew
```

Then in the EC2 console, select the instance → **Instance state → Stop**. Stopped instances do not charge for CPU. A stopped instance still costs a few cents a day for the disk and, if you keep it, the public IPv4 address.

To end every charge, **Terminate** the instance and delete the volume.

SQLite and uploaded resumes live inside the container disk. Stopping the container without removing it keeps them. Terminating the instance deletes them.

---

## Update the running demo

From your machine, copy the changed files again, then on the instance:

```bash
cd ~/careercrew
docker rm -f careercrew
docker build -t careercrew .
docker run -d --name careercrew --restart unless-stopped \
  -p 7860:7860 --env-file .env careercrew
```

---

## If it fails

| What you see | What to change |
|--------------|----------------|
| Browser times out | Security group must allow TCP 7860 from your IP. Confirm `docker ps` shows `0.0.0.0:7860->7860/tcp`. |
| **Limited mode** | `.env` has no `OPENAI_API_KEY`, or the container was started without `--env-file .env`. |
| Container exits during Analyze | Out of memory. Stay on `t3.medium` (4 GB). Do not use a GPU. |
| Sample buttons fail | The image must contain `COPY samples ./samples`. Rebuild after pulling. |
| SSH refused | Port 22 is limited to My IP, and your IP changed. Edit the security group. |
