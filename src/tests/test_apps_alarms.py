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


def test_spanish_icon_label_matches_without_package_name(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.camera"]
    platform.app_label_map = {"com.example.camera": ("Cámara", "Camera")}
    assert open_app(platform, "camara", tmp_path / "missing.json") == "com.example.camera"
    assert platform.opened_apps == ["com.example.camera"]


@pytest.mark.parametrize("heard, label", [("oxide", "Obsidian"), ("pita", "Picta")])
def test_observed_voice_mishearing_uses_icon_label(tmp_path, heard, label):
    platform = DesktopPlatform()
    platform.packages = ["com.example.target"]
    platform.app_label_map = {"com.example.target": (label,)}
    assert open_app(platform, heard, tmp_path / "missing.json") == "com.example.target"
    assert platform.opened_apps == ["com.example.target"]


def test_real_app_name_takes_priority_over_voice_correction(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.pita", "com.example.picta"]
    platform.app_label_map = {
        "com.example.pita": ("Pita",), "com.example.picta": ("Picta",)
    }
    assert open_app(platform, "pita", tmp_path / "missing.json") == "com.example.pita"
    assert platform.opened_apps == ["com.example.pita"]


def test_close_icon_name_launches_unique_app(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.notes", "com.example.camera"]
    platform.app_label_map = {
        "com.example.notes": ("Obsidian",), "com.example.camera": ("Cámara",)
    }
    assert open_app(platform, "obsidiana", tmp_path / "missing.json") == "com.example.notes"
    assert platform.opened_apps == ["com.example.notes"]


def test_pista_transcript_selects_picta_with_clear_lead(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.picta", "com.android.systemui", "com.example.bitchat"]
    platform.app_label_map = {
        "com.example.picta": ("Picta",),
        "com.android.systemui": ("UI sistema",),
        "com.example.bitchat": ("bitchat",),
    }
    assert open_app(platform, "pista", tmp_path / "missing.json") == "com.example.picta"
    assert platform.opened_apps == ["com.example.picta"]


def test_pista_transcript_does_not_guess_between_close_apps(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.picta", "com.example.pistax"]
    platform.app_label_map = {
        "com.example.picta": ("Picta",), "com.example.pistax": ("PistaX",)
    }
    with pytest.raises(ValueError, match="Closest icon names: PistaX, Picta"):
        open_app(platform, "pista", tmp_path / "missing.json")
    assert platform.opened_apps == []


def test_fuzzy_app_match_requires_clear_lead(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.camas", "com.example.camao"]
    platform.app_label_map = {
        "com.example.camas": ("Camas",), "com.example.camao": ("Camao",)
    }
    with pytest.raises(ValueError, match="Closest icon names: Camao, Camas"):
        open_app(platform, "cama", tmp_path / "missing.json")
    assert platform.opened_apps == []


def test_fuzzy_app_match_rejects_short_or_distant_names(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.camera"]
    platform.app_label_map = {"com.example.camera": ("Cámara",)}
    for name in ("cam", "table"):
        with pytest.raises(ValueError, match="App not found"):
            open_app(platform, name, tmp_path / "missing.json")
    assert platform.opened_apps == []


def test_duplicate_icon_labels_do_not_launch(tmp_path):
    platform = DesktopPlatform()
    platform.packages = ["com.example.one", "com.example.two"]
    platform.app_label_map = {"com.example.one": ("Notas",), "com.example.two": ("Notas",)}
    with pytest.raises(ValueError, match="Multiple apps match"):
        open_app(platform, "notas", tmp_path / "missing.json")
    assert platform.opened_apps == []


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
        if args[:2] == ["pm", "resolve-activity"]:
            return subprocess.CompletedProcess(
                args, 0, "com.google.android.youtube/com.google.android.youtube.HomeActivity\n", ""
            )
        return subprocess.CompletedProcess(args, 0, "Starting: Intent", "")

    monkeypatch.setattr(subprocess, "run", run)
    platform = AndroidPlatform()
    open_app(platform, "youtube")
    set_alarm(platform, 7, 30)
    assert commands[0] == ["pm", "list", "packages", "--user", "0"]
    assert commands[1][:5] == ["pm", "resolve-activity", "--brief", "--components", "--user"]
    assert commands[2] == ["am", "start", "--user", "0", "-a", "android.intent.action.MAIN",
                           "-c", "android.intent.category.LAUNCHER",
                           "-n", "com.google.android.youtube/com.google.android.youtube.HomeActivity"]
    assert commands[3] == ["am", "start", "--user", "0", "-a", "android.intent.action.SET_ALARM",
                           "--ei", "android.intent.extra.alarm.HOUR", "7",
                           "--ei", "android.intent.extra.alarm.MINUTES", "30",
                           "--ez", "android.intent.extra.alarm.SKIP_UI", "true"]


def test_android_whatsapp_command_does_not_list_packages(monkeypatch, tmp_path):
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
    assert commands[0][:2] == ["pm", "resolve-activity"]
    assert commands[1] == ["am", "start", "--user", "0", "-a", "android.intent.action.MAIN",
                           "-c", "android.intent.category.LAUNCHER",
                           "-n", "com.whatsapp/com.whatsapp.Main"]
    assert len(commands) == 2


@pytest.mark.parametrize("telegram_package", [
    "org.telegram.messenger",
    "org.telegram.messenger.web",
])
def test_android_telegram_command_ignores_framework_package(monkeypatch, tmp_path,
                                                            telegram_package):
    monkeypatch.chdir(tmp_path)
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[:3] == ["pm", "list", "packages"]:
            return subprocess.CompletedProcess(
                args, 0, f"package:android\npackage:{telegram_package}\n", ""
            )
        if args[:2] == ["pm", "resolve-activity"]:
            return subprocess.CompletedProcess(
                args, 0, f"{telegram_package}/org.telegram.messenger.DefaultIcon\n", ""
            )
        if "-p" in args:
            return subprocess.CompletedProcess(args, 1, "", "unable to resolve Intent")
        return subprocess.CompletedProcess(args, 0, "Starting: Intent", "")

    monkeypatch.setattr(subprocess, "run", run)
    main(["abre telegram", "--platform", "android", "--execute"])
    assert commands[2] == ["am", "start", "--user", "0",
                           "-a", "android.intent.action.MAIN",
                           "-c", "android.intent.category.LAUNCHER",
                           "-n", f"{telegram_package}/org.telegram.messenger.DefaultIcon"]


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


def test_android_rejects_launcher_component_from_other_package(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs:
                        subprocess.CompletedProcess(args, 0, "com.bad.app/.Main\n", ""))
    with pytest.raises(ValueError, match="invalid launcher activity"):
        AndroidPlatform().open_app("com.example.app")


def test_android_app_labels_are_cached_and_refreshed(monkeypatch, tmp_path):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[:2] == ["pm", "path"]:
            return subprocess.CompletedProcess(args, 0, "package:/data/app/example/base.apk\n", "")
        if args[:3] == ["aapt", "dump", "badging"]:
            return subprocess.CompletedProcess(
                args, 0,
                "application-label:'Camera'\napplication-label-es:'Cámara'\n"
                "launchable-activity: name='com.example.camera.Main'  label='Camera' icon=''\n", ""
            )
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("platform_api.android.shutil.which", lambda name: "/termux/bin/aapt")
    platform = AndroidPlatform(tmp_path / "app-labels.json")
    expected = {"com.example.camera": ("Cámara", "Camera")}
    assert platform.app_labels(["android", "com.example.camera"]) == expected
    assert platform.app_labels(["android", "com.example.camera"]) == expected
    assert len(commands) == 2
    assert platform.app_labels(["android", "com.example.camera"], refresh=True) == expected
    assert len(commands) == 4


def test_android_app_labels_require_aapt(monkeypatch, tmp_path):
    monkeypatch.setattr("platform_api.android.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="pkg install aapt"):
        AndroidPlatform(tmp_path / "missing.json").app_labels(["com.example.camera"])


def test_android_app_labels_skip_unreadable_apk(monkeypatch, tmp_path):
    def run(args, **kwargs):
        if args[:2] == ["pm", "path"]:
            if args[-1] == "com.example.hidden":
                raise subprocess.TimeoutExpired(args, 15)
            return subprocess.CompletedProcess(args, 0, "package:/data/app/visible/base.apk\n", "")
        return subprocess.CompletedProcess(args, 0, "application-label:'Visible'\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("platform_api.android.shutil.which", lambda name: "/termux/bin/aapt")
    labels = AndroidPlatform(tmp_path / "app-labels.json").app_labels(
        ["com.example.hidden", "com.example.visible"]
    )
    assert labels == {"com.example.hidden": (), "com.example.visible": ("Visible",)}


def test_index_apps_cli_refreshes_labels(monkeypatch, capsys):
    platform = Mock(spec=AndroidPlatform)
    platform.installed_packages.return_value = ["android", "com.example.camera"]
    platform.app_labels.return_value = {"com.example.camera": ("Cámara",)}
    monkeypatch.setattr("platform_api.android.AndroidPlatform", lambda: platform)
    main(["--platform", "android", "--index-apps"])
    platform.app_labels.assert_called_once_with(
        ["android", "com.example.camera"], refresh=True
    )
    assert "Indexed icon names for 1 app." in capsys.readouterr().out


def test_unknown_app_without_launcher_fails_before_am(monkeypatch):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "No activity found\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="Cannot find launcher activity"):
        AndroidPlatform().open_app("com.example.unlaunchable")
    assert len(commands) == 1
