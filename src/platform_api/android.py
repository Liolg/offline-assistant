import subprocess
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from platform_api.base import Platform, validate_recording_seconds


class AndroidPlatform(Platform):
    """Existing Termux adapter; only used when explicitly instantiated."""

    def flashlight(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        subprocess.run(
            [
                "termux-torch",
                "on" if enabled else "off",
            ],
            check=True,
            timeout=10,
        )

    @staticmethod
    def _microphone(*args: str) -> str:
        return subprocess.run(
            ["termux-microphone-record", *args], check=True, timeout=15,
            capture_output=True, text=True,
        ).stdout.strip()

    def _recording_status(self) -> dict:
        try:
            status = json.loads(self._microphone("-i"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("Cannot read microphone status; check Termux:API microphone permission") from exc
        if not isinstance(status, dict) or type(status.get("isRecording")) is not bool:
            raise RuntimeError("Unexpected Termux microphone status")
        return status

    def record_audio(self, destination: Path, seconds: int) -> None:
        """Capture AAC with Termux, wait for completion, then convert locally."""
        validate_recording_seconds(seconds)
        if self._recording_status()["isRecording"]:
            raise RuntimeError("A microphone recording is already in progress")
        with TemporaryDirectory(prefix="assistant-mic-") as directory:
            source = Path(directory) / "command.m4a"
            started = False
            try:
                response = self._microphone("-f", str(source), "-e", "aac", "-l", str(seconds))
                started = response.startswith(f"Recording started: {source}")
                status = self._recording_status()
                started = status["isRecording"] and status.get("outputFile") == str(source)
                if not started:
                    raise RuntimeError(f"Microphone did not start: {response}")
                print(f"Recording for {seconds} seconds. Speak now.", flush=True)
                time.sleep(seconds)
                for _ in range(5):
                    status = self._recording_status()
                    if not status["isRecording"]:
                        started = False
                        break
                    if status.get("outputFile") != str(source):
                        started = False
                        raise RuntimeError("Microphone recording was replaced by another recording")
                    time.sleep(1)
                else:
                    raise RuntimeError("Microphone did not finish within the recording limit")
            finally:
                if started:
                    self._microphone("-q")
            if not source.is_file() or source.stat().st_size == 0:
                raise RuntimeError("Microphone produced no audio file; check microphone permission")
            result = subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-i", str(source), "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", str(destination)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode:
                raise RuntimeError(f"Audio conversion failed: {result.stderr.strip()}")
