# Local Run Findings

## Machine Snapshot (one developer machine — not project defaults)

- OS: Windows 11 Home, build 26200
- RAM: 32 GB
- GPU: NVIDIA GeForce RTX 3080, 10 GB VRAM
- Node: v22.22.0
- Docker: not installed on PATH at start of setup
- WSL: not installed at start of setup
- Python: not installed on PATH at start of setup
- uv: not installed on PATH at start of setup

## Setup Attempt

Attempted Docker Desktop installation through `winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements --silent`.

Result:

- Installer downloaded and verified successfully.
- The installer requested administrator execution.
- The install exited with code `4294967291`.
- `docker` remained unavailable on PATH afterward.

Because Docker Desktop and WSL2 are not installed yet, the stack could not be started with `docker compose up -d`, models could not be pulled into the Ollama container, and browser smoke testing could not proceed in this session.

## Next Manual Action

Run these from an elevated Windows session or complete the UAC prompts manually:

```powershell
wsl --install
winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
```

After any required reboot, verify:

```powershell
docker --version
docker compose version
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
```

Then start the stack and pull the models named in your `.env` (defaults are in `.env.example`; recommended tiers are in `ROADMAP.md`):

```powershell
docker compose up -d
docker exec signalquay-ollama ollama pull qwen2.5:32b
docker exec signalquay-ollama ollama pull nomic-embed-text
```

## Note On `.env`

`.env` is gitignored. Any per-machine tuning (smaller LLMs for limited VRAM, fewer rounds for quick tests, etc.) belongs only in your local `.env` and does not change committed defaults in `.env.example` or `backend/app/config.py`.
