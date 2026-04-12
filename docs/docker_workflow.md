# Docker Workflow

This repo is now Docker-first for local development.

## Why

- Reproducible backend and frontend runtime
- Minimal host dependency setup
- Source code, `dev_mem/`, and `library/` stay in the repo and remain editable
- Cleaner path toward future deployment

## Services

### Backend

- Image: `python:3.12-slim`
- Entrypoint: `uvicorn backend.app.main:app`
- Default compose mode: `--reload`
- Default market source in compose: `mock`
- Kraken CLI is installed into the image during build and exposed on the container `PATH`
- Python dependencies are installed into the image; the host virtualenv is irrelevant inside Docker

### Frontend

- Image: `node:20-bookworm-slim`
- Entrypoint: Vite dev server on port `5173`
- Bind-mounted source for live editing
- Named volume for `node_modules`

## Secret injection

The backend supports both:

- direct environment variables such as `OPENAI_API_KEY`
- a mounted read-only config file at `/run/secrets/api_key.conf`

Compose mounts:

- `./api_secret` on the host
- `/run/secrets` in the backend container

The secret directory is part of the workspace shape, but actual secret files should stay uncommitted.

## Host port overrides

Compose defaults to publishing:

- backend on `8000`
- frontend on `5173`

If those ports are busy on the host, run compose with `BACKEND_PORT` and `FRONTEND_PORT` overrides.

## Runtime truth

- Host mode can use host-local env vars or any reachable key file path.
- Docker mode uses container-local env vars and the mounted `/run/secrets` path from repo-local `api_secret/`.
- Missing LLM credentials still produce the existing safe backend chat fallback.
- Missing or failing Kraken live reads still fall back to mock snapshots.
- Live Kraken mode in Docker should only be treated as available after `kraken --version` and an actual market read are verified in that container.
