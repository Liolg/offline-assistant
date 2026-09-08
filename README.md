# Offline assistant

Python foundation for an offline Android voice assistant. The default demo uses
a mocked flashlight without runtime dependencies. An optional Needle 2 adapter
turns typed commands into validated tool-call proposals. Optional Vosk transcription
accepts English or Spanish recordings. Microphone capture is not implemented yet.

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
  assistant/native_needle.py # Local executable adapter; no SDK required
  assistant/voice.py         # Local Vosk WAV transcription, English or Spanish
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
even in Termux, the demo uses the desktop mock. Select Android explicitly with
`--platform android` and enable execution with `--execute`. The manual native
Needle → Python → Termux:API test was reported successful offline on an ARM64
Android 14 phone with Python 3.14.6. The integrated CLI has PC mock coverage;
verify it on your phone after pulling changes.

The remaining empty modules are placeholders from the original scaffold.
Vosk transcription feeds the same brain interface. Calls, SMS, and other tools
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
them to a fresh desktop mock. Desktop remains the default platform.
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
Android. Use the Android executable path below for native Termux.
The regular pytest suite uses fake Needle responses and requires no model or network.

## Native Needle in Termux

Install Termux and the Termux:API Android app from the same source, then install
the command-line packages. Update packages together before adding dependencies:

```sh
apt update
apt full-upgrade
apt install python curl termux-api
```

From the repository root, download the official Android ARM64 executable once:

```sh
mkdir -p models/needle
curl -fL --retry 3 \
  https://huggingface.co/Cactus-Compute/needle2/resolve/main/android-arm64/needle \
  -o models/needle/needle
chmod +x models/needle/needle
```

Preview a proposed call (no Python SDK installation needed):

```sh
PYTHONPATH=src python -m offline_assistant.main "turn on the flashlight" \
  --needle-bin models/needle/needle --platform android
```

Add `--execute` to control the phone:

```sh
PYTHONPATH=src python -m offline_assistant.main "turn on the flashlight" \
  --needle-bin models/needle/needle --platform android --execute
PYTHONPATH=src python -m offline_assistant.main "turn off the flashlight" \
  --needle-bin models/needle/needle --platform android --execute
```

The light remains in its requested state; there is no automatic shutoff. You can
also run `termux-torch off` directly. Repeat these commands with Wi-Fi and mobile
data disabled to verify offline operation.

The native adapter starts a process for each command, writes the current schema
to a temporary file, and removes it afterward. No manually maintained `tools.json`
is needed. Inference has a 30-second timeout; Android torch commands have a
10-second timeout. `--execute-mock` is retained for desktop use and is rejected
with `--platform android`.

Commit source, `pyproject.toml`, and `uv.lock`; virtual environments and downloaded
models are ignored. Keep future models under `models/` and download them separately
on each device. Clone/pull the source in Termux and create an environment there;
do not copy the PC virtual environment to Android.

## English and Spanish recordings

On PC/WSL, install the optional speech runtime (add `--extra needle` if using the
Needle Python SDK instead of a native executable):

```sh
uv sync --python 3.12 --extra voice
```

Download and extract both small models from the official
[Vosk model catalog](https://alphacephei.com/vosk/models) while connected:

```sh
mkdir -p models
curl -fL --retry 3 https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip \
  -o models/vosk-model-small-en-us-0.15.zip
curl -fL --retry 3 https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip \
  -o models/vosk-model-small-es-0.42.zip
unzip models/vosk-model-small-en-us-0.15.zip -d models
unzip models/vosk-model-small-es-0.42.zip -d models
```

Use one language per recording: `--language en` selects US English and
`--language es` selects Spanish. This version does not detect the language or
switch languages mid-recording. Only the selected model is loaded, by local
directory path; the application does not download models. `--models-dir` overrides
the parent directory while keeping the extracted model directory names above.

Store your recordings in ignored `recordings/`. Audio must be mono, 16-bit PCM WAV
at 16000 Hz. Convert a recording with a separately installed FFmpeg if necessary:

```sh
mkdir -p recordings
ffmpeg -i input.m4a -ac 1 -ar 16000 -c:a pcm_s16le recordings/command.wav
```

Check recognition independently of Needle or Android:

```sh
PYTHONPATH=src python -m offline_assistant.main \
  --audio recordings/english.wav --language en --transcribe-only
PYTHONPATH=src python -m offline_assistant.main \
  --audio recordings/spanish.wav --language es --transcribe-only
```

Once the transcript is correct, preview the complete flow:

```sh
PYTHONPATH=src python -m offline_assistant.main \
  --audio recordings/spanish.wav --language es \
  --needle-bin models/needle/needle
```

Use an executable built for the machine running the command. On a phone with a
working Vosk runtime, add `--platform android --execute` to perform the action.
Silence does not load Needle or execute anything. Invalid recordings, missing
models, and transcription failures stop the command. Transcripts are printed so
you can review what was recognized; model selection confidence is not a measure
of transcription accuracy.

Spanish text is passed to Needle unchanged. Evaluate examples such as
“enciende la linterna” and “apaga la linterna” in preview mode before execution;
recognition support alone does not establish reliable Spanish tool selection.

Native Termux Vosk Python installation and audio inference are not yet verified.
The available Android Vosk SDK and Linux Python wheels are different deployment
paths; do not assume a Linux ARM64 wheel loads in Termux. First check
`python -c "import vosk; print('Vosk import OK')"` on the phone and use its result
to determine the next setup step. The existing typed Android flow works without
Vosk. Regular pytest tests use generated WAV data and fake recognizers, with no
model downloads or network access.
