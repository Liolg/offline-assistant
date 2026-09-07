from abc import ABC, abstractmethod


class Platform(ABC):
    """Device operations available to tools, independent of the host OS."""

    @abstractmethod
    def flashlight(self, enabled: bool) -> None:
        """Set the flashlight state; raise an exception if the operation fails."""
