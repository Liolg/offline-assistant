# Offline assistant

Python foundation for an offline Android voice assistant. The default demo uses
a mocked flashlight without runtime dependencies. An optional Needle 2 adapter
turns typed commands into validated tool-call proposals. Microphone capture and
Vosk are not implemented yet.

## Run on PC / WSL

Use Python 3.11 or newer. With uv:

```sh
uv sync --python 3.12
uv run --python 3.12 offline-assistant
uv run --python 3.12 pytest
```

Or use a regular virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . --group dev
python -m offline_assistant.main
python -m pytest
```

If your pip does not support `--group`, use `python -m pip install -e . pytest`.
Installation requires downloaded packages; the installed demo runs fully offline.
The existing `.python-version` selects Python 3.15 for uv; the commands above
explicitly select 3.12. Use an available Python >=3.11 on your machine.

Expected output:

```text
[MOCK] flashlight: on
[MOCK] flashlight: off
```

## Current structure and boundaries

The repository's existing `src/` layout is retained:

```text
src/
  offline_assistant/main.py  # Demo and console entry point
  assistant/config.py       # Explicit desktop mock factory
  assistant/brain.py        # Optional Needle adapter; proposals only
  assistant/tool_calls.py   # Model-independent structured requests
  assistant/executor.py     # Validation and allowlisted dispatch
  platform_api/base.py      # Platform contract: flashlight(bool)
  platform_api/desktop.py   # In-memory mock with observable state
  platform_api/android.py   # Existing Termux torch adapter
  tools/system.py           # Validated flashlight tool
  tests/                    # pytest tests
```

The tool receives a platform instance instead of importing a global device.
`Platform` defines only the operation currently needed. `DesktopPlatform` stores
state per instance, and the demo handles presentation. Invalid non-boolean inputs
are rejected before dispatch, and platform errors propagate to the caller.

The existing Android torch adapter implements the same interface and invokes
`termux-torch` via a subprocess argument list. It is never selected automatically;
even in Termux, the demo uses the desktop mock. Real Android behavior is not
validated in this milestone. A future Android integration will require Termux:API
setup and device testing.

The remaining empty modules are placeholders from the original scaffold. Future
Vosk transcription can feed the same brain interface. Calls, SMS, and other tools
are not supported; they require a confirmation and authorization layer before
being added to the executor.

## Typed commands with Needle 2

Install the optional runtime and explicitly download its engine while connected:

```sh
uv sync --python 3.12 --extra needle
NEEDLE_TELEMETRY=0 uv run --python 3.12 --extra needle needle fetch --generation 2
```

Then run the installed application directly (no package resolution at runtime):

```sh
.venv/bin/offline-assistant "turn on the flashlight"
.venv/bin/offline-assistant "turn on the flashlight" --execute-mock
```

The first command prints proposed calls without execution. The second applies
them to a fresh desktop mock. No Android platform is selected by this CLI.
Needle receives JSON schemas, not executable tool functions, and uses `complete()`.
The executor independently checks every proposed call before any call is executed.
Unknown tools, extra arguments, and non-boolean flashlight states are rejected.
Device failures propagate; already executed actions are not rolled back.

Each input starts a fresh model conversation. Empty proposals do nothing.
Nonempty proposals require a numeric confidence of at least 0.8; this initial
threshold needs evaluation on real command examples and is not authorization.
Failed or malformed responses exit with an error.

The adapter sets `HF_HUB_OFFLINE=1` and `NEEDLE_TELEMETRY=0` before loading Needle,
disabling downloads and SDK usage telemetry during commands. A missing engine
fails with a setup error. The engine cache is outside Git;
see the upstream [offline setup documentation](https://github.com/cactus-compute/needle/blob/main/doc/apis.md#offline-devices)
for cache locations and library overrides. A PC engine binary is not portable to
Android. Native Termux compatibility and on-device inference still need validation.
The regular pytest suite uses fake Needle responses and requires no model or network.

Commit source, `pyproject.toml`, and `uv.lock`; virtual environments and downloaded
models are ignored. Keep future models under `models/` and download them separately
on each device. Clone/pull the source in Termux and create an environment there;
do not copy the PC virtual environment to Android.
