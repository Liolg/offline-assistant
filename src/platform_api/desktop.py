from pathlib import Path
import wave

from platform_api.base import Contact, Platform, validate_recording_seconds


class DesktopPlatform(Platform):
    """In-memory device mock. Performs no system commands or hardware access."""

    def __init__(self, contacts: list[Contact] | None = None) -> None:
        self.flashlight_enabled = False
        self.contacts = list(contacts or [])
        self.called_numbers: list[str] = []
        self.packages: list[str] = []
        self.app_label_map: dict[str, tuple[str, ...]] = {}
        self.opened_apps: list[str] = []
        self.alarms: list[tuple[int, int]] = []

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

    def installed_packages(self) -> list[str]:
        return list(self.packages)

    def app_labels(self, packages: list[str], *, refresh: bool = False) -> dict[str, tuple[str, ...]]:
        return {package: self.app_label_map.get(package, ()) for package in packages}

    def open_app(self, package: str) -> None:
        self.opened_apps.append(package)

    def set_alarm(self, hour: int, minute: int) -> None:
        self.alarms.append((hour, minute))
