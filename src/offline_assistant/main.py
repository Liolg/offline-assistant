from assistant.config import create_platform
from tools.system import flashlight


def main() -> None:
    """Demonstrate the flashlight tool using an explicitly mocked device."""
    platform = create_platform()
    for enabled in (True, False):
        flashlight(platform, enabled)
        state = "on" if platform.flashlight_enabled else "off"
        print(f"[MOCK] flashlight: {state}")


if __name__ == "__main__":
    main()
