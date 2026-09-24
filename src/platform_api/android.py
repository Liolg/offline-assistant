import subprocess
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from platform_api.base import Contact, Platform, validate_recording_seconds


KNOWN_LAUNCH_COMPONENTS = {
    "com.whatsapp": "com.whatsapp/com.whatsapp.Main",
    "org.telegram.messenger": "org.telegram.messenger/org.telegram.ui.LaunchActivity",
    "org.telegram.messenger.web": "org.telegram.messenger.web/org.telegram.ui.LaunchActivity",
}
ACTIVITY_NAME = re.compile(r"\.?[A-Za-z_$][A-Za-z0-9_.$]*")


class AndroidPlatform(Platform):
    """Existing Termux adapter; only used when explicitly instantiated."""

    def __init__(self, app_cache_path: Path | None = None) -> None:
        self.app_cache_path = app_cache_path or Path.home() / ".cache/offline-assistant/app-labels.json"

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

    def list_contacts(self) -> list[Contact]:
        """Read Termux:API contacts without retaining the full address book."""
        result = subprocess.run(
            ["termux-contact-list"], check=True, timeout=15,
            capture_output=True, text=True,
        )
        try:
            records = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("Termux returned invalid contacts JSON") from exc
        if not isinstance(records, list):
            raise ValueError("Termux returned an invalid contact list")
        contacts = []
        for record in records:
            if (not isinstance(record, dict) or
                    not isinstance(record.get("name"), str) or
                    not isinstance(record.get("number"), str)):
                raise ValueError("Termux returned an invalid contact")
            contacts.append(Contact(record["name"], record["number"]))
        return contacts

    def call_phone(self, number: str) -> None:
        subprocess.run(["termux-telephony-call", number], check=True, timeout=15)

    def installed_packages(self) -> list[str]:
        result = subprocess.run(
            ["pm", "list", "packages", "--user", "0"], check=True, timeout=15,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
        )
        packages = []
        for line in result.stdout.splitlines():
            if not line.startswith("package:") or not line[8:]:
                raise ValueError("Android returned an invalid package list")
            packages.append(line[8:])
        return packages

    def _package_labels(self, package: str) -> tuple[str, ...]:
        """Read the labels stored in one installed APK; skip unreadable APKs."""
        try:
            result = subprocess.run(
                ["pm", "path", "--user", "0", package], check=False, timeout=15,
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return ()
        if result.returncode != 0:
            return ()
        paths = [line.removeprefix("package:") for line in result.stdout.splitlines()
                 if line.startswith("package:")]
        if not paths:
            return ()
        apk = next((path for path in paths if path.endswith("/base.apk")), paths[0])
        try:
            result = subprocess.run(
                ["aapt", "dump", "badging", apk], check=False, timeout=20,
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("App label matching requires aapt; run pkg install aapt in Termux") from exc
        except (OSError, subprocess.SubprocessError):
            return ()
        if result.returncode != 0:
            return ()
        spanish = []
        default = []
        for line in result.stdout.splitlines():
            match = re.fullmatch(r"application-label(?:-([\w-]+))?:'(.*)'", line)
            if match and match.group(2):
                if match.group(1) and match.group(1).startswith("es"):
                    spanish.append(match.group(2))
                elif not match.group(1):
                    default.append(match.group(2))
            if line.startswith("launchable-activity:"):
                match = re.search(r"\blabel='([^']+)'", line)
                if match:
                    default.append(match.group(1))
        return tuple(dict.fromkeys([*spanish, *default]))

    def app_labels(self, packages: list[str], *, refresh: bool = False) -> dict[str, tuple[str, ...]]:
        """Cache icon labels locally; a full APK scan is needed only on changes."""
        current = sorted(set(packages))
        if not refresh:
            try:
                cached = json.loads(self.app_cache_path.read_text(encoding="utf-8"))
                if cached.get("packages") == current and isinstance(cached.get("labels"), dict):
                    labels = cached["labels"]
                    if all(isinstance(labels.get(package), list) and
                           all(isinstance(label, str) for label in labels[package])
                           for package in current if package != "android"):
                        return {package: tuple(labels[package])
                                for package in current if package != "android"}
            except (OSError, ValueError, AttributeError):
                pass
        if shutil.which("aapt") is None:
            raise RuntimeError("App label matching requires aapt; run pkg install aapt in Termux")
        labels = {package: self._package_labels(package) for package in current if package != "android"}
        self.app_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.app_cache_path.write_text(
            json.dumps({"packages": current, "labels": labels}, ensure_ascii=False),
            encoding="utf-8",
        )
        return labels

    @staticmethod
    def _launcher_component(package: str) -> str:
        try:
            result = subprocess.run(
                ["pm", "resolve-activity", "--brief", "--components", "--user", "0",
                 "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER",
                 "-p", package],
                check=False, timeout=15, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            if package in KNOWN_LAUNCH_COMPONENTS:
                return KNOWN_LAUNCH_COMPONENTS[package]
            raise RuntimeError(f"Cannot find launcher activity for {package}: {exc}") from exc
        if result.returncode != 0 or result.stdout.strip() == "No activity found":
            if package in KNOWN_LAUNCH_COMPONENTS:
                return KNOWN_LAUNCH_COMPONENTS[package]
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"Cannot find launcher activity for {package}: {detail or 'none found'}")
        lines = result.stdout.strip().splitlines()
        component = lines[-1] if lines else ""
        owner, slash, activity = component.partition("/")
        if not slash or owner != package or not ACTIVITY_NAME.fullmatch(activity):
            raise ValueError(f"Android returned an invalid launcher activity for {package}: {component}")
        return component

    @staticmethod
    def _start_activity(args: list[str]) -> None:
        result = subprocess.run(
            ["am", "start", "--user", "0", *args], check=False, timeout=15,
            capture_output=True, text=True,
        )
        output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0 or any(marker in output.casefold() for marker in
               ("error:", "error type", "exception", "permission denial", "unable to resolve")):
            raise RuntimeError(f"Android could not start activity: {output or f'exit status {result.returncode}'}")

    def open_app(self, package: str) -> None:
        component = self._launcher_component(package)
        self._start_activity([
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            "-n", component,
        ])

    def set_alarm(self, hour: int, minute: int) -> None:
        self._start_activity([
            "-a", "android.intent.action.SET_ALARM",
            "--ei", "android.intent.extra.alarm.HOUR", str(hour),
            "--ei", "android.intent.extra.alarm.MINUTES", str(minute),
            "--ez", "android.intent.extra.alarm.SKIP_UI", "true",
        ])

    @staticmethod
    def _microphone(*args: str) -> str:
        return subprocess.run(
            ["termux-microphone-record", *args], check=True, timeout=15,
            capture_output=True, text=True,
        ).stdout.strip()

    def _recording_status(self) -> dict:
        try:
            status = json.loads(self._microphone("-i"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("Cannot read microphone status; check Termux:API microphone permission") from exc
        if not isinstance(status, dict) or type(status.get("isRecording")) is not bool:
            raise RuntimeError("Unexpected Termux microphone status")
        return status

    def record_audio(self, destination: Path, seconds: int) -> None:
        """Capture AAC with Termux, wait for completion, then convert locally."""
        validate_recording_seconds(seconds)
        if self._recording_status()["isRecording"]:
            raise RuntimeError("A microphone recording is already in progress")
        with TemporaryDirectory(prefix="assistant-mic-") as directory:
            source = Path(directory) / "command.m4a"
            started = False
            try:
                response = self._microphone("-f", str(source), "-e", "aac", "-l", str(seconds))
                started = response.startswith(f"Recording started: {source}")
                status = self._recording_status()
                started = status["isRecording"] and status.get("outputFile") == str(source)
                if not started:
                    raise RuntimeError(f"Microphone did not start: {response}")
                print(f"Recording for {seconds} seconds. Speak now.", flush=True)
                time.sleep(seconds)
                for _ in range(5):
                    status = self._recording_status()
                    if not status["isRecording"]:
                        started = False
                        break
                    if status.get("outputFile") != str(source):
                        started = False
                        raise RuntimeError("Microphone recording was replaced by another recording")
                    time.sleep(1)
                else:
                    raise RuntimeError("Microphone did not finish within the recording limit")
            finally:
                if started:
                    self._microphone("-q")
            if not source.is_file() or source.stat().st_size == 0:
                raise RuntimeError("Microphone produced no audio file; check microphone permission")
            result = subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-i", str(source), "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", str(destination)],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode:
                raise RuntimeError(f"Audio conversion failed: {result.stderr.strip()}")
