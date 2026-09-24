from pathlib import Path
import wave

from platform_api.base import Contact, Platform, validate_recording_seconds


class DesktopPlatform(Platform):
    """In-memory device mock. Performs no system commands or hardware access."""

    def __init__(self, contacts: list[Contact] | None = None) -> None:
        self.flashlight_enabled = False
        self.contacts = list(contacts or [])
        self.called_numbers: list[str] = []

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

    def list_contacts(self) -> list[Contact]:
        return list(self.contacts)

    def call_phone(self, number: str) -> None:
        self.called_numbers.append(number)
