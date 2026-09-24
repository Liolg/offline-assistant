import json
import subprocess
from unittest.mock import Mock

import pytest

from assistant.executor import Executor
from assistant.tool_calls import ToolCall, direct_open_app, direct_set_alarm
from offline_assistant.main import main
from platform_api.android import AndroidPlatform
from platform_api.desktop import DesktopPlatform
from tools.alarms import set_alarm
from tools.apps import open_app


@pytest.mark.parametrize("text, name", [
    ("abre YouTube", "YouTube"),
    ("abrir la aplicación WhatsApp", "WhatsApp"),
    ("open Google Maps", "Google Maps"),
])
def test_direct_app_command(text, name):
    assert direct_open_app(text) == ToolCall("open_app", {"name": name})


def test_spanish_recording_opens_unique_installed_app(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    platform = DesktopPlatform()
    platform.packages = ["com.google.android.youtube", "com.android.chrome"]
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    monkeypatch.setattr("offline_assistant.main.NativeNeedleClient",
                        Mock(side_effect=AssertionError("Needle must not load")))
    voice = Mock(transcribe=Mock(return_value="abre youtube"))
    main(["--record", "--language", "es", "--needle-bin", "missing", "--execute-mock"],
         transcriber=voice)
    assert platform.opened_apps == ["com.google.android.youtube"]


def test_app_preview_does_not_query_packages(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    platform = Mock(spec=DesktopPlatform)
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    main(["abre YouTube"])
    platform.installed_packages.assert_not_called()
    platform.open_app.assert_not_called()


def test_local_app_alias_matches_installed_package(tmp_path):
    aliases = tmp_path / "apps.json"
    aliases.write_text(json.dumps({"mi música": "com.spotify.music"}), encoding="utf-8")
    platform = DesktopPlatform()
    # Explicit aliases can launch apps hidden from Android's package listing.
    open_app(platform, "mi música", aliases)
    assert platform.opened_apps == ["com.spotify.music"]


def test_whatsapp_uses_known_package_without_discovery(tmp_path):
    platform = Mock(spec=DesktopPlatform)
    platform.installed_packages.side_effect = subprocess.CalledProcessError(
        2, ["pm", "list", "packages"]
    )
    assert open_app(platform, "whatsapp", tmp_path / "missing.json") == "com.whatsapp"
    platform.installed_packages.assert_not_called()
    platform.open_app.assert_called_once_with("com.whatsapp")


def test_local_alias_overrides_known_whatsapp_package(tmp_path):
    aliases = tmp_path / "apps.json"
    aliases.write_text('{"whatsapp": "com.whatsapp.w4b"}', encoding="utf-8")
    platform = Mock(spec=DesktopPlatform)
    assert open_app(platform, "whatsapp", aliases) == "com.whatsapp.w4b"
    platform.installed_packages.assert_not_called()
    platform.open_app.assert_called_once_with("com.whatsapp.w4b")


def test_package_discovery_failure_suggests_alias(tmp_path):
    platform = Mock(spec=DesktopPlatform)
    platform.installed_packages.side_effect = subprocess.CalledProcessError(
        2, ["pm", "list", "packages"]
    )
    with pytest.raises(RuntimeError, match="apps.json"):
        open_app(platform, "youtube", tmp_path / "missing.json")
    platform.open_app.assert_not_called()


def test_exact_package_suffix_wins_over_related_app(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.google.android.youtube", "com.google.android.apps.youtube.music"]
    open_app(platform, "youtube", tmp_path / "missing.json")
    assert platform.opened_apps == ["com.google.android.youtube"]


def test_android_framework_package_does_not_block_app_resolution(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["android", "org.telegram.messenger"]
    assert open_app(platform, "telegram", tmp_path / "missing.json") == "org.telegram.messenger"
    assert platform.opened_apps == ["org.telegram.messenger"]


@pytest.mark.parametrize("packages, name, message", [
    ([], "YouTube", "App not found"),
    (["com.foo.music", "com.bar.music"], "music", "Multiple apps match"),
    (["bad;package"], "bad", "invalid package identifier"),
])
def test_app_resolution_fails_without_launch(tmp_path, packages, name, message):
    platform = DesktopPlatform()
    platform.packages = packages
    with pytest.raises(ValueError, match=message):
        open_app(platform, name, tmp_path / "missing.json")
    assert platform.opened_apps == []


def test_bad_alias_file_fails_without_launch(tmp_path):
    aliases = tmp_path / "apps.json"
    aliases.write_text('{"youtube": "bad;package"}', encoding="utf-8")
    platform = DesktopPlatform()
    platform.packages = ["com.google.android.youtube"]
    with pytest.raises(ValueError, match="App aliases"):
        open_app(platform, "youtube", aliases)
    assert platform.opened_apps == []


@pytest.mark.parametrize("text, hour, minute", [
    ("pon una alarma a las 7:30", 7, 30),
    ("pon una alarma a las siete y media", 7, 30),
    ("programa la alarma para las 7 de la tarde", 19, 0),
    ("configura alarma a las 6 de la mañana", 6, 0),
    ("poner una alarma a las 12 de la noche", 0, 0),
    ("pon una alarma a las 19:45", 19, 45),
])
def test_direct_alarm_command(text, hour, minute):
    assert direct_set_alarm(text) == ToolCall("set_alarm", {"hour": hour, "minute": minute})


@pytest.mark.parametrize("text", ["pon una alarma a las 24:00", "pon una alarma a las 7:70"])
def test_invalid_spoken_alarm_never_falls_back_to_needle(monkeypatch, text):
    monkeypatch.setattr("offline_assistant.main.NeedleBrain.load",
                        Mock(side_effect=AssertionError("Needle must not load")))
    with pytest.raises(SystemExit) as error:
        main([text, "--execute"])
    assert error.value.code == 1


def test_spanish_recording_sets_alarm_without_needle(monkeypatch):
    platform = DesktopPlatform()
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    monkeypatch.setattr("offline_assistant.main.NativeNeedleClient",
                        Mock(side_effect=AssertionError("Needle must not load")))
    voice = Mock(transcribe=Mock(return_value="pon una alarma a las siete y media"))
    main(["--record", "--language", "es", "--needle-bin", "missing", "--execute-mock"],
         transcriber=voice)
    assert platform.alarms == [(7, 30)]


@pytest.mark.parametrize("hour, minute", [(24, 0), (-1, 0), (7, 60), (True, 0), (7, False)])
def test_bad_alarm_time_never_reaches_platform(hour, minute):
    platform = DesktopPlatform()
    with pytest.raises(ValueError):
        set_alarm(platform, hour, minute)
    assert platform.alarms == []


def test_invalid_alarm_proposal_is_rejected_before_execution():
    platform = DesktopPlatform()
    with pytest.raises(ValueError):
        Executor(platform).validate_proposal([ToolCall("set_alarm", {"hour": 7, "minute": 60})])
    assert platform.alarms == []


def test_android_uses_literal_commands_for_app_and_alarm(monkeypatch):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[:3] == ["pm", "list", "packages"]:
            assert kwargs["stdin"] == subprocess.DEVNULL
            assert kwargs["capture_output"] is True
            return subprocess.CompletedProcess(args, 0, "package:com.google.android.youtube\n", "")
        return subprocess.CompletedProcess(args, 0, "Starting: Intent", "")

    monkeypatch.setattr(subprocess, "run", run)
    platform = AndroidPlatform()
    open_app(platform, "youtube")
    set_alarm(platform, 7, 30)
    assert commands[0] == ["pm", "list", "packages", "--user", "0"]
    assert commands[1] == ["am", "start", "--user", "0", "-a", "android.intent.action.MAIN",
                           "-c", "android.intent.category.LAUNCHER",
                           "-p", "com.google.android.youtube"]
    assert commands[2] == ["am", "start", "--user", "0", "-a", "android.intent.action.SET_ALARM",
                           "--ei", "android.intent.extra.alarm.HOUR", "7",
                           "--ei", "android.intent.extra.alarm.MINUTES", "30",
                           "--ez", "android.intent.extra.alarm.SKIP_UI", "true"]


def test_android_whatsapp_command_does_not_run_pm(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[0] == "pm":
            raise subprocess.CalledProcessError(2, args)
        if "-p" in args:
            return subprocess.CompletedProcess(args, 1, "", "unable to resolve Intent")
        return subprocess.CompletedProcess(args, 0, "Starting: Intent", "")

    monkeypatch.setattr(subprocess, "run", run)
    main(["abre whatsapp", "--platform", "android", "--execute"])
    assert commands == [["am", "start", "--user", "0", "-a", "android.intent.action.MAIN",
                         "-c", "android.intent.category.LAUNCHER",
                         "-n", "com.whatsapp/com.whatsapp.Main"]]


def test_android_telegram_command_ignores_framework_package(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[:3] == ["pm", "list", "packages"]:
            return subprocess.CompletedProcess(
                args, 0, "package:android\npackage:org.telegram.messenger\n", ""
            )
        if "-p" in args:
            return subprocess.CompletedProcess(args, 1, "", "unable to resolve Intent")
        return subprocess.CompletedProcess(args, 0, "Starting: Intent", "")

    monkeypatch.setattr(subprocess, "run", run)
    main(["abre telegram", "--platform", "android", "--execute"])
    assert commands[1] == ["am", "start", "--user", "0",
                           "-a", "android.intent.action.MAIN",
                           "-c", "android.intent.category.LAUNCHER",
                           "-n", "org.telegram.messenger/org.telegram.ui.LaunchActivity"]


@pytest.mark.parametrize("output", ["Error: Activity not found", "Error type 3", "Security exception: Permission Denial"])
def test_android_activity_error_propagates(monkeypatch, output):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs:
                        subprocess.CompletedProcess(args, 0, output, ""))
    with pytest.raises(RuntimeError, match="could not start activity"):
        AndroidPlatform().set_alarm(7, 30)


def test_android_activity_nonzero_exit_includes_system_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs:
                        subprocess.CompletedProcess(args, 1, "", "Permission Denial: blocked"))
    with pytest.raises(RuntimeError, match="Permission Denial: blocked"):
        AndroidPlatform().open_app("com.whatsapp")
