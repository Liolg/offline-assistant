# Repository Guidelines

## Project Structure & Module Organization

This Python 3.11+ project uses a `src/` layout. `src/offline_assistant/main.py`
provides the demo and console entry point. `src/assistant/config.py` creates the
default platform. `src/platform_api/` contains the platform contract, desktop mock,
and existing Android adapter. Device-independent tools belong in `src/tools/`;
pytest tests belong in `src/tests/`. Other assistant and tool modules are currently
placeholders. Store future downloaded models in ignored `models/` directories.

## Build, Test, and Development Commands

- `uv sync --python 3.12`: install the project and development dependencies.
- `uv run --python 3.12 offline-assistant`: demonstrate mocked flashlight on/off.
- `uv run --python 3.12 pytest`: run the test suite.
- `uv build`: build the source distribution and wheel in `dist/`.

The Python override avoids the existing `.python-version` selection of 3.15.
With an activated environment and the project installed, use
`python -m offline_assistant.main` and `python -m pytest` instead.

## Existing Android Widget Shortcut

The user's Obsidian widget launches the assistant through this Termux script:

```bash
#!/data/data/com.termux/files/usr/bin/bash
exec /data/data/com.termux/files/usr/bin/bash \
  "$HOME/offline-assistant/run-assistant" \
  --record --language es --platform android \
  --needle-bin models/needle/needle --seconds 5 \
  --execute
```

It records a five-second Spanish command and executes validated actions on the
Android device. The launcher resolves the relative Needle path from the repository
directory. Changes to voice commands should account for this existing shortcut.
The direct call parser accepts Spanish phrases such as `llama a mamá`; if no
Spanish mother contact matches, the name resolves to a contact saved as `Mom`.

## Coding Style & Naming Conventions

Use four-space indentation, type hints for public functions, and short docstrings
for contracts and non-obvious behavior. Use `snake_case` for functions and modules,
`PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Follow existing
imports and style; no formatter or linter is configured.

## Architecture & Security

Pass platform instances into tools rather than accessing global devices. Keep
Android commands inside `platform_api/android.py`. Preserve the desktop mock as
the demo default, including in Termux. Validate tool inputs before dispatch and
propagate platform failures. Keep future Vosk and Needle integrations separate
from execution; dangerous actions such as calls or SMS require a confirmation
and authorization layer. Do not commit virtual environments or downloaded models.
Update `uv.lock` when dependencies change.

## Testing Guidelines

Name files `test_*.py` and functions `test_*`. Use pytest and mocks to verify state
changes, invalid inputs, platform failures, and isolation from hardware. Desktop
tests must run without Android commands, models, or network access. No coverage
threshold is configured. Run the suite before submitting changes; report Android
device validation separately.

## Commit & Pull Request Guidelines

Git history contains only `Initial commit`, so no established commit convention
exists. Use concise imperative subjects, such as `Add flashlight input validation`.
Describe the problem, resulting behavior, and validation in pull requests. Link
related issues when applicable, and identify untested Android behavior or new
setup requirements. Update README instructions when commands or architecture change.
