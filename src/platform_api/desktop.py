from platform_api.base import Platform


class DesktopPlatform(Platform):
    """In-memory device mock. Performs no system commands or hardware access."""

    def __init__(self) -> None:
        self.flashlight_enabled = False

    def flashlight(self, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be a bool")
        self.flashlight_enabled = enabled
