import argparse
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from assistant.brain import Brain, NeedleBrain
from assistant.config import create_platform
from assistant.executor import Executor
from assistant.native_needle import NativeNeedleClient
from assistant.voice import Transcriber, VoskTranscriber
from tools.system import flashlight


def main(
    argv: list[str] | None = None,
    *,
    brain: Brain | None = None,
    transcriber: Transcriber | None = None,
) -> None:
    """Preview typed tool calls, or explicitly execute them on a chosen platform."""
    parser = argparse.ArgumentParser(description="Offline typed or recorded flashlight commands")
    parser.add_argument("command", nargs="?", help="A quoted natural-language command")
    audio_input = parser.add_mutually_exclusive_group()
    audio_input.add_argument("--audio", help="Local mono, 16-bit, 16000 Hz PCM WAV recording")
    audio_input.add_argument("--record", action="store_true", help="Record a command using the selected platform")
    parser.add_argument("--seconds", type=int, help="Recording duration, 1–30 seconds (default: 8)")
    parser.add_argument("--language", choices=["en", "es"], help="Recording language (required with --audio or --record)")
    parser.add_argument("--models-dir", help="Vosk model parent directory (default: models)")
    parser.add_argument("--transcribe-only", action="store_true", help="Print the transcript without loading Needle")
    parser.add_argument("--platform", choices=["desktop", "android"], default="desktop")
    parser.add_argument("--needle-bin", help="Path to a native Needle executable (no SDK needed)")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--execute", action="store_true", help="Execute on the selected platform")
    execution.add_argument(
        "--execute-mock", action="store_true", help="Execute validated calls on DesktopPlatform"
    )
    args = parser.parse_args(argv)
    has_audio = args.audio or args.record
    if has_audio and args.command is not None:
        parser.error("Choose a typed command, --audio, or --record")
    if has_audio and not args.language:
        parser.error("--audio and --record require --language en or es")
    if args.seconds is not None and (not args.record or not 1 <= args.seconds <= 30):
        parser.error("--seconds requires --record and must be from 1 to 30")
    if not has_audio and (args.language or args.models_dir or args.transcribe_only):
        parser.error("Language, model, and transcription options require --audio or --record")
    if args.transcribe_only and (
        args.execute or args.execute_mock or args.needle_bin or (args.platform != "desktop" and not args.record)
    ):
        parser.error("--transcribe-only cannot be combined with engine, platform, or execution options")
    if args.execute_mock and args.platform != "desktop":
        parser.error("--execute-mock requires --platform desktop")
    if args.command is None and not has_audio and (
        args.execute or args.execute_mock or args.needle_bin or args.platform != "desktop"
    ):
        parser.error("Platform, engine, and execution options require a command")
    if args.platform == "android":
        from platform_api.android import AndroidPlatform

        platform = AndroidPlatform()
    else:
        platform = create_platform()
    if has_audio:
        try:
            voice = transcriber if transcriber is not None else VoskTranscriber(args.models_dir or "models")
            if args.record:
                with TemporaryDirectory(prefix="assistant-voice-") as directory:
                    recording = Path(directory) / "command.wav"
                    if args.platform == "desktop":
                        print("[MOCK] Generating silent audio; desktop recording does not use a microphone.")
                    platform.record_audio(recording, args.seconds or 8)
                    args.command = voice.transcribe(str(recording), args.language).strip()
            else:
                args.command = voice.transcribe(args.audio, args.language).strip()
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            parser.exit(1, f"Error: {exc}\n")
        except KeyboardInterrupt:
            parser.exit(130, "Recording cancelled; no action executed.\n")
        print(f"Transcript ({args.language}): {args.command}")
        if not args.command:
            print("No speech recognized; no action proposed.")
            return
        if args.transcribe_only:
            return
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
