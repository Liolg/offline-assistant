from platform_api.desktop import DesktopPlatform


def create_platform() -> DesktopPlatform:
    """Default to a fresh mock on every host, including Termux."""
    return DesktopPlatform()
