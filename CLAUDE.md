# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## What this is

**tydom2mqtt** is a bridge that connects a Deltadore **Tydom** home-automation
gateway to an **MQTT** broker, exposing devices to Home Assistant via MQTT
discovery. It is a long-running async Python service, shipped as a Docker image.

## Layout

All source lives under [`app/`](app):

- [`app/main.py`](app/main.py) — entry point; wires up the clients and runs the
  asyncio event loop (`listen_tydom`, `poll_device_tydom`, MQTT connect).
- [`app/configuration/`](app/configuration) — `Configuration.load()`, reads all
  settings from environment variables with sane defaults.
- [`app/tydom/`](app/tydom) — `TydomClient` (websocket connection to the
  gateway) and `MessageHandler` (triage of incoming Tydom messages).
- [`app/mqtt/`](app/mqtt) — `MqttClient`, built on `gmqtt`.
- [`app/sensors/`](app/sensors) — one module per device type (`Cover`, `Light`,
  `Alarm`, `Boiler`, `Switch`, `Garage`, `ShHvac`, `AutomaticDoor`, …). Each
  handles its own Home Assistant MQTT discovery + state publishing.

Docs are in [`docs/`](docs) (docsify site). User-facing config is documented there.

## Dev workflow

Dependencies (run from `app/`):

```bash
cd app && pip install -r requirements.txt -r requirements.dev.txt
```

Lint & format — this project uses **Ruff** (the CI is the source of truth):

```bash
cd app && ruff format .      # apply formatting
cd app && ruff format --check .
cd app && ruff check .       # lint
```

> Note: `DEV.md` still mentions `autopep8`, but CI enforces **Ruff** — use Ruff.

Tests:

```bash
cd app && pytest
```

Build & run the container:

```bash
docker build -t tydom2mqtt .
docker run -it --rm -e TYDOM_MAC="001A25123456" -e TYDOM_PASSWORD="secret" tydom2mqtt
```

## Conventions

- **Config comes from env vars only.** Add new settings in
  [`Configuration.py`](app/configuration/Configuration.py) (constant + default)
  and document them in `docs/`. Do not read env vars elsewhere.
- **Logging, not print.** Use `logger = logging.getLogger(__name__)` and
  `logger.info("msg %s", value)` (lazy `%s` formatting, not f-strings in log
  calls).
- **Async everywhere.** The service runs on a single asyncio loop; never block
  it with synchronous I/O.
- **New device types** go in their own module under `app/sensors/`, following an
  existing sensor as a template (Home Assistant MQTT discovery + state topics).
- **Commits / PR titles are semantic** (Conventional Commits, e.g.
  `feat:`, `fix:`, `chore:`). The CI `semantic-pr` job enforces this and the
  changelog/release is generated from it.

## CI

[`.github/workflows/ci.yaml`](.github/workflows/ci.yaml) runs Ruff (format +
lint), pytest, and a Docker build on every PR. The semantic PR title check
runs separately in
[`.github/workflows/semantic-pr.yaml`](.github/workflows/semantic-pr.yaml).
[`.github/workflows/release_build.yaml`](.github/workflows/release_build.yaml)
builds and pushes the multi-arch image to GHCR on version tags (`*.*.*`) and
manual dispatch.

Python is pinned to **3.11** (matches the Dockerfile base image).

## Reviewing changes

See [`REVIEW.md`](REVIEW.md) for the recommended PR review process
(the `pr-review-toolkit` plugin).
