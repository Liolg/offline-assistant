import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from assistant.brain import FLASHLIGHT_SCHEMA


class NativeNeedleClient:
    """Run the local Needle executable without the optional Python SDK."""

    def __init__(self, executable: str) -> None:
        self.executable = str(Path(executable).expanduser().resolve())

    def reset(self) -> None:
        """Each invocation starts a fresh process and conversation."""

    def complete(self, text: str) -> object:
        # Generate from the current schema so a downloaded tools.json cannot drift.
        with TemporaryDirectory(prefix="offline-assistant-") as directory:
            schema = Path(directory) / "tools.json"
            schema.write_text(json.dumps([FLASHLIGHT_SCHEMA]), encoding="utf-8")
            try:
                result = subprocess.run(
                    [self.executable, "--tools", str(schema), "--prompt", text],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                    timeout=30,
                    env={**os.environ, "HF_HUB_OFFLINE": "1", "NEEDLE_TELEMETRY": "0"},
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Needle inference timed out after 30 seconds") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    f"Needle exited with status {exc.returncode}: {(exc.stderr or '').strip()}"
                ) from exc
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("Needle returned invalid JSON") from exc
