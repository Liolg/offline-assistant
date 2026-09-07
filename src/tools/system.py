from platform_api.base import Platform


def flashlight(platform: Platform, enabled: bool) -> None:
    """Validate a flashlight request and delegate it to the supplied platform."""
    if not isinstance(enabled, bool):
        raise TypeError("enabled must be a bool")
    platform.flashlight(enabled)
