# Offline assistant

Initial Python foundation for an offline Android voice assistant. This milestone
only demonstrates a mocked flashlight, with no runtime dependencies, network
access, microphone access, speech recognition, or model downloads.

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

The remaining empty modules are placeholders from the original scaffold. Vosk,
Needle, a dispatcher, and other tools are not implemented. Future speech recognition
and tool selection should feed a separate execution layer, with confirmation and
authorization before dangerous operations such as calls or SMS. Model selection
must not itself execute actions. Cached-model offline behavior remains future work.

Commit source, `pyproject.toml`, and `uv.lock`; virtual environments and downloaded
models are ignored. Keep future models under `models/` and download them separately
on each device. Clone/pull the source in Termux and create an environment there;
do not copy the PC virtual environment to Android.
