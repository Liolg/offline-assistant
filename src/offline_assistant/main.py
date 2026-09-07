import argparse
import json
from dataclasses import asdict

from assistant.brain import Brain, NeedleBrain
from assistant.config import create_platform
from assistant.executor import Executor
from tools.system import flashlight


def main(argv: list[str] | None = None, *, brain: Brain | None = None) -> None:
    """Preview typed tool calls, or explicitly execute them on a mock."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", help="A quoted natural-language command")
    parser.add_argument(
        "--execute-mock", action="store_true", help="Execute validated calls on DesktopPlatform"
    )
    args = parser.parse_args(argv)
    platform = create_platform()
    if args.command is not None:
        executor = Executor(platform)
        try:
            calls = (brain if brain is not None else NeedleBrain.load()).propose(args.command)
            # Validate the entire proposal before the first possible side effect.
            for call in calls:
                executor.validate(call)
            print(json.dumps([asdict(call) for call in calls]))
            if not calls:
                print("No supported action proposed.")
            elif args.execute_mock:
                for call in calls:
                    executor.execute(call)
                    state = "on" if platform.flashlight_enabled else "off"
                    print(f"[MOCK] flashlight: {state}")
            else:
                print("Preview only. Use --execute-mock to execute on the desktop mock.")
        except (ValueError, RuntimeError, OSError) as exc:
            parser.exit(1, f"Error: {exc}\n")
        return
    if args.execute_mock:
        parser.error("--execute-mock requires a command")
    for enabled in (True, False):
        flashlight(platform, enabled)
        state = "on" if platform.flashlight_enabled else "off"
        print(f"[MOCK] flashlight: {state}")


if __name__ == "__main__":
    main()
