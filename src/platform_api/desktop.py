from pathlib import Path
import wave

from platform_api.base import Platform, validate_recording_seconds


class DesktopPlatform(Platform):
    """In-memory device mock. Performs no system commands or hardware access."""

    def __init__(self) -> None:
        self.flashlight_enabled = False

    def flashlight(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        self.flashlight_enabled = enabled

    def record_audio(self, destination: Path, seconds: int) -> None:
        """Generate silent audio without microphone access or waiting."""
        validate_recording_seconds(seconds)
        with wave.open(str(destination), "wb") as recording:
            recording.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            recording.writeframes(bytes(seconds * 16000 * 2))
