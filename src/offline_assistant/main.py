import argparse
import json
import subprocess
from dataclasses import asdict

from assistant.brain import Brain, NeedleBrain
from assistant.config import create_platform
from assistant.executor import Executor
from assistant.native_needle import NativeNeedleClient
from tools.system import flashlight


def main(argv: list[str] | None = None, *, brain: Brain | None = None) -> None:
    """Preview typed tool calls, or explicitly execute them on a chosen platform."""
    parser = argparse.ArgumentParser(description="Offline typed flashlight commands")
    parser.add_argument("command", nargs="?", help="A quoted natural-language command")
    parser.add_argument("--platform", choices=["desktop", "android"], default="desktop")
    parser.add_argument("--needle-bin", help="Path to a native Needle executable (no SDK needed)")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--execute", action="store_true", help="Execute on the selected platform")
    execution.add_argument(
        "--execute-mock", action="store_true", help="Execute validated calls on DesktopPlatform"
    )
    args = parser.parse_args(argv)
    if args.execute_mock and args.platform != "desktop":
        parser.error("--execute-mock requires --platform desktop")
    if args.command is None and (
        args.execute or args.execute_mock or args.needle_bin or args.platform != "desktop"
    ):
        parser.error("Platform, engine, and execution options require a command")
    if args.platform == "android":
        from platform_api.android import AndroidPlatform

        platform = AndroidPlatform()
    else:
        platform = create_platform()
    if args.command is not None:
        executor = Executor(platform)
        try:
            if brain is None:
                brain = (
                    NeedleBrain(NativeNeedleClient(args.needle_bin))
                    if args.needle_bin else NeedleBrain.load()
                )
            calls = brain.propose(args.command)
            # Validate the entire proposal before the first possible side effect.
            for call in calls:
                executor.validate(call)
            print(json.dumps([asdict(call) for call in calls]))
            if not calls:
                print("No supported action proposed.")
            elif args.execute or args.execute_mock:
                for call in calls:
                    executor.execute(call)
                    state = "on" if call.arguments["enabled"] else "off"
                    label = "ANDROID" if args.platform == "android" else "MOCK"
                    print(f"[{label}] flashlight: {state}")
            else:
                print(f"Preview only. Use --execute to execute on {args.platform}.")
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            parser.exit(1, f"Error: {exc}\n")
        return
    for enabled in (True, False):
        flashlight(platform, enabled)
        state = "on" if platform.flashlight_enabled else "off"
        print(f"[MOCK] flashlight: {state}")


if __name__ == "__main__":
    main()
