# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A "Live Q&A" web app built with FastAPI, at an early stage (only the Stage 0 skeleton is committed). Dependencies point to server-rendered pages: Jinja2 templates (`templates/`, still empty) and form posts (`python-multipart`), served by uvicorn.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                                   # install deps, including the dev group
uv run uvicorn app.main:app --reload      # run the dev server
uv run pytest                             # run all tests
uv run pytest tests/test_health.py::test_health   # run a single test
uv run ruff check .                       # lint
uv run ruff format .                      # format
```

## Layout notes

- **The real application is the top-level `app/` package** (`app/main.py` defines the FastAPI `app`). `src/presentation_app/` is the leftover `uv init` stub behind the `presentation-app` console script and the `uv_build` backend; it is not the web app. Note that `uv_build` packages only `src/`, so `app/` is not included in a built wheel.
- Tests import `app.main` directly. This works because `pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["."]`. Tests use FastAPI's `TestClient`, which is why `httpx` is a dev dependency.

## Stack
- FastAPI + Jinja2 templates + htmx (from CDN). No frontend build step.
- SQLite via the standard library `sqlite3`. No ORM.
- Python tooling is `uv`. Never use pip directly.

## Commands
- Tests: `uv run pytest -q`
- Lint & format: `uv run ruff check --fix . && uv run ruff format .`
- Dev server: `uv run uvicorn app.main:app --reload --port 8000`

## Structure
- `app/main.py`: routes only
- `app/db.py`: all SQL lives here
- `templates/`: Jinja2 templates; htmx partials start with `_` (e.g. `_questions.html`)
- `tests/`: one test file per module

## Rules
- Every new endpoint gets a test in the same change.
- DB path comes from env var `QA_DB_PATH` (default `qa.db`). Tests use a temporary DB, never `qa.db`.
- Do not add dependencies without asking me first.
- Never read or modify `.env`.
- Run tests and ruff before saying a task is done.
- Edit files only with the Edit/Write tools, never with sed, redirects or other shell commands.
- Never delete or weaken existing tests without asking me first.