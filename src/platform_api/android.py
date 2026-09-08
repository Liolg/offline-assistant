import subprocess

from platform_api.base import Platform


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
