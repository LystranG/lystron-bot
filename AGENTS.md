# Repository Guidelines

## Project Structure & Module Organization

- `bot.py` is the entrypoint. It initializes NoneBot, registers adapters (OneBot V11 + Console), and loads local plugins via `nonebot.load_plugins("plugin")`.
- `plugin/` contains first-party plugins. Each plugin lives in its own package directory, for example `plugin/anti_recall/__init__.py`.
- `.env` holds local runtime configuration (host/port/driver, OneBot token, plugin settings). Treat it as a secret file and avoid committing credentials.

## Build, Test, and Development Commands

This repo is a lightweight script-based bot (no build step).

```bash
# Run locally
python bot.py
```

If you’re setting up a fresh environment, install the minimum deps implied by imports:

```bash
python -m venv .venv
source .venv/bin/activate
pip install nonebot2 nonebot-adapter-onebot nonebot-adapter-console pydantic
```

## Coding Style & Naming Conventions

- Python: 4-space indentation, follow PEP 8, prefer explicit type hints (`list[int]`, `dict[...]`) and async handlers (`async def`).
- Plugins: use `snake_case` for plugin directories and keep the main entry in `plugin/<name>/__init__.py`. Provide `__plugin_meta__` for name/description/usage.
- Formatting/linting: no enforced tooling in this repo yet. Recommended: `black` (format) + `ruff` (lint) if you add CI later.

## Testing Guidelines

There is currently no automated test suite. If you add tests:

- Use `pytest`, place tests under `tests/`, and name files `test_*.py`.
- Run with `pytest -q`.

## Commit & Pull Request Guidelines

- No existing Git commit history in this repository yet; use Conventional Commits going forward (e.g., `feat: add anti-recall forward`, `fix: handle missing config`).
- PRs should include: what changed, how to run it (`python bot.py`), any `.env` keys added/changed (redact secrets), and tests when applicable.

## Security & Configuration Tips

- Do not commit secrets (e.g., `ACCESS_TOKEN`) or personal identifiers unless required for functionality and approved.
- Prefer adding a sanitized `.env.example` when introducing new configuration keys.
