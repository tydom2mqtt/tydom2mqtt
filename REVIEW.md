# Code Review Guide

This project reviews pull requests with the **`pr-review-toolkit`** Claude Code
plugin. It bundles a set of specialized review agents and a one-shot
orchestration command so every PR gets a consistent, thorough review.

## Why this plugin

A single "look over my code" pass misses things. `pr-review-toolkit` splits the
review into focused agents that each look for one class of problem — bugs,
silent failures, weak types, missing tests, comment rot — which catches far more
than a generic review and keeps feedback actionable.

## Install

In Claude Code, add the marketplace and install the plugin:

```
/plugin marketplace add anthropics/claude-code
/plugin install pr-review-toolkit
```

Then restart Claude Code (or reload plugins) so the agents and commands appear.

## Usage

Run the full review on your current changes:

```
/pr-review-toolkit:review-pr
```

This orchestrates the specialized agents below and aggregates their findings.
By default review the **unstaged diff** (`git diff`); for a specific PR or
branch, tell the command which changes to focus on.

### Agents available

Invoke any of these directly when you only need one lens:

- **code-reviewer** — adherence to project guidelines (`CLAUDE.md`), style and
  best practices.
- **silent-failure-hunter** — `try/except` blocks and fallbacks that swallow
  errors. Especially relevant here: the asyncio loops in
  [`app/main.py`](app/main.py) catch broad `Exception`s — make sure new code
  doesn't hide real failures.
- **pr-test-analyzer** — test coverage and edge cases for new functionality.
- **type-design-analyzer** — quality of new types / dataclasses (e.g. additions
  to [`Configuration.py`](app/configuration/Configuration.py)).
- **comment-analyzer** — accuracy of comments and docstrings.
- **code-simplifier** — clarity and maintainability of recently written code,
  preserving behavior.

## Project-specific things to check

- New config is read **only** in
  [`Configuration.py`](app/configuration/Configuration.py) and documented in
  `docs/`.
- New device types follow the existing `app/sensors/` modules (Home Assistant
  MQTT discovery + state publishing).
- Logging uses lazy `%s` formatting, no blocking I/O on the asyncio loop.
- PR title is a semantic / Conventional Commit (`feat:`, `fix:`, `chore:` …) —
  the CI `semantic-pr` job enforces this.
- Ruff (format + lint) and pytest pass — see
  [`.github/workflows/ci.yaml`](.github/workflows/ci.yaml).

See [`CLAUDE.md`](CLAUDE.md) for the full set of project conventions.
