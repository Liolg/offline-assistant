from abc import ABC, abstractmethod
from pathlib import Path


class Platform(ABC):
    """Device operations available to tools, independent of the host OS."""

    @abstractmethod
    def flashlight(self, enabled: bool) -> None:
        """Set the flashlight state; raise an exception if the operation fails."""

    @abstractmethod
    def record_audio(self, destination: Path, seconds: int) -> None:
        """Write a completed mono, 16-bit, 16 kHz PCM WAV to destination."""


def validate_recording_seconds(seconds: int) -> None:
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("Recording duration must be an integer from 1 to 30 seconds")
