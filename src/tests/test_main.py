from unittest.mock import Mock

import pytest

from assistant.config import create_platform
from assistant.tool_calls import ToolCall
from offline_assistant.main import main
from platform_api.desktop import DesktopPlatform


def test_demo_stays_mocked_in_termux(monkeypatch, capsys):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")

    def unexpected_command(*args, **kwargs):
        raise AssertionError("The demo must not execute system commands")

    monkeypatch.setattr("subprocess.run", unexpected_command)
    assert isinstance(create_platform(), DesktopPlatform)
    main([])
    assert capsys.readouterr().out == (
        "[MOCK] flashlight: on\n[MOCK] flashlight: off\n"
    )


@pytest.mark.parametrize("execute", [False, True])
def test_typed_command_preview_and_execution(monkeypatch, capsys, execute):
    platform = DesktopPlatform()
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    brain = Mock()
    brain.propose.return_value = [ToolCall("flashlight", {"enabled": True})]
    args = ["turn on the flashlight"] + (["--execute-mock"] if execute else [])
    main(args, brain=brain)
    assert platform.flashlight_enabled is execute
    assert '"name": "flashlight"' in capsys.readouterr().out


def test_entire_proposal_is_validated_before_execution(monkeypatch, capsys):
    platform = DesktopPlatform()
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    brain = Mock()
    brain.propose.return_value = [
        ToolCall("flashlight", {"enabled": True}), ToolCall("call_contact", {"name": "Alice"})
    ]
    with pytest.raises(SystemExit) as error:
        main(["turn on flashlight and call Alice", "--execute-mock"], brain=brain)
    assert error.value.code == 1
    assert platform.flashlight_enabled is False
    assert "Unsupported tool" in capsys.readouterr().err


@pytest.mark.parametrize("execute", [False, True])
def test_android_requires_explicit_execution(monkeypatch, capsys, execute):
    from platform_api.base import Platform

    platform = Mock(spec=Platform)
    monkeypatch.setattr("platform_api.android.AndroidPlatform", lambda: platform)
    brain = Mock()
    brain.propose.return_value = [ToolCall("flashlight", {"enabled": True})]
    main(["on", "--platform", "android"] + (["--execute"] if execute else []), brain=brain)
    if execute:
        platform.flashlight.assert_called_once_with(True)
        assert "[ANDROID] flashlight: on" in capsys.readouterr().out
    else:
        platform.flashlight.assert_not_called()


@pytest.mark.parametrize("args", [
    ["on", "--platform", "android", "--execute-mock"],
    ["--platform", "android"], ["--execute"], ["--needle-bin", "needle"],
])
def test_ambiguous_execution_options_are_rejected(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


def test_cli_native_engine_selection(monkeypatch, capsys):
    client = Mock()
    client.complete.return_value = {
        "type": "call", "success": True, "confidence": 1,
        "function_calls": [{"name": "flashlight", "arguments": {"enabled": False}}],
    }
    factory = Mock(return_value=client)
    monkeypatch.setattr("offline_assistant.main.NativeNeedleClient", factory)
    main(["off", "--needle-bin", "models/needle/needle", "--execute"])
    factory.assert_called_once_with("models/needle/needle")
    assert "[MOCK] flashlight: off" in capsys.readouterr().out


@pytest.mark.parametrize("language, text", [("en", "turn on the flashlight"), ("es", "enciende la linterna")])
@pytest.mark.parametrize("execute", [False, True])
def test_audio_flows_to_brain_with_explicit_execution(monkeypatch, capsys, language, text, execute):
    platform = DesktopPlatform()
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    voice = Mock()
    voice.transcribe.return_value = text
    brain = Mock()
    brain.propose.return_value = [ToolCall("flashlight", {"enabled": True})]
    main(["--audio", "command.wav", "--language", language] + (["--execute"] if execute else []),
         brain=brain, transcriber=voice)
    voice.transcribe.assert_called_once_with("command.wav", language)
    brain.propose.assert_called_once_with(text)
    assert platform.flashlight_enabled is execute
    assert f"Transcript ({language}): {text}" in capsys.readouterr().out


@pytest.mark.parametrize("text, transcribe_only", [("", False), ("  ", False), ("enciende la linterna", True)])
def test_transcription_can_stop_without_loading_needle(monkeypatch, text, transcribe_only):
    voice = Mock()
    voice.transcribe.return_value = text
    load = Mock(side_effect=AssertionError("Needle must not load"))
    monkeypatch.setattr("offline_assistant.main.NeedleBrain.load", load)
    main(["--audio", "command.wav", "--language", "es"] +
         (["--transcribe-only"] if transcribe_only else []), transcriber=voice)
    load.assert_not_called()


def test_transcription_error_never_reaches_brain(capsys):
    voice, brain = Mock(), Mock()
    voice.transcribe.side_effect = ValueError("bad recording")
    with pytest.raises(SystemExit) as error:
        main(["--audio", "bad.wav", "--language", "en", "--execute"], brain=brain, transcriber=voice)
    assert error.value.code == 1
    brain.propose.assert_not_called()
    assert "bad recording" in capsys.readouterr().err


@pytest.mark.parametrize("args", [
    ["--audio", "command.wav"],
    ["on", "--audio", "command.wav", "--language", "en"],
    ["--language", "es"], ["--transcribe-only"], ["--models-dir", "models"],
    ["--audio", "command.wav", "--language", "en", "--transcribe-only", "--execute"],
])
def test_audio_option_errors(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
