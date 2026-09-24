from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Contact:
    """A named phone number returned by the selected platform."""

    name: str
    number: str


class Platform(ABC):
    """Device operations available to tools, independent of the host OS."""

    @abstractmethod
    def flashlight(self, enabled: bool) -> None:
        """Set the flashlight state; raise an exception if the operation fails."""

    @abstractmethod
    def record_audio(self, destination: Path, seconds: int) -> None:
        """Write a completed mono, 16-bit, 16 kHz PCM WAV to destination."""

    @abstractmethod
    def list_contacts(self) -> list[Contact]:
        """Return contacts with phone numbers; raise if lookup fails."""

    @abstractmethod
    def call_phone(self, number: str) -> None:
        """Place a phone call to a previously validated number."""

    @abstractmethod
    def installed_packages(self) -> list[str]:
        """Return installed Android package identifiers visible to the platform."""

    @abstractmethod
    def app_labels(self, packages: list[str], *, refresh: bool = False) -> dict[str, tuple[str, ...]]:
        """Return available icon labels for the given installed packages."""

    @abstractmethod
    def open_app(self, package: str) -> None:
        """Launch an application's main activity."""

    @abstractmethod
    def set_alarm(self, hour: int, minute: int) -> None:
        """Request a one-time alarm at the specified local time of day."""


def validate_recording_seconds(seconds: int) -> None:
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("Recording duration must be an integer from 1 to 30 seconds")
