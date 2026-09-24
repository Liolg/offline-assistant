import json
import subprocess
from unittest.mock import Mock

import pytest

from assistant.tool_calls import ToolCall, direct_contact_call
from offline_assistant.main import main
from platform_api.android import AndroidPlatform
from platform_api.base import Contact
from platform_api.desktop import DesktopPlatform
from tools.phone import call_contact, normalize_number


def test_typed_call_preview_does_not_read_contacts(monkeypatch, capsys):
    platform = DesktopPlatform([Contact("Mom", "+53 5555 1234")])
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    brain = Mock(propose=Mock(return_value=[ToolCall("call_contact", {"name": "Mom"})]))
    main(["call mom"], brain=brain)
    assert platform.called_numbers == []
    assert '"name": "call_contact"' in capsys.readouterr().out


def test_typed_call_executes_one_exact_contact(monkeypatch, capsys):
    platform = DesktopPlatform([Contact("Mom", "+53 5555 1234")])
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    brain = Mock(propose=Mock(return_value=[ToolCall("call_contact", {"name": "  mom "})]))
    main(["call mom", "--execute-mock"], brain=brain)
    assert platform.called_numbers == ["+5355551234"]
    assert "Calling Mom (+5355551234)..." in capsys.readouterr().out


@pytest.mark.parametrize("text, name", [
    ("call mom", "mom"), ("CALL Mom", "Mom"),
    ("call Mom Smith.", "Mom Smith"),
])
def test_literal_call_command_is_recognized(text, name):
    assert direct_contact_call(text) == ToolCall("call_contact", {"name": name})


@pytest.mark.parametrize("text", ["call", "call .", "please call mom", "recall mom"])
def test_other_phrases_still_use_brain(text):
    assert direct_contact_call(text) is None


def test_literal_call_skips_needle_confidence(monkeypatch):
    platform = DesktopPlatform([Contact("Mom", "5551234")])
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    monkeypatch.setattr("offline_assistant.main.NeedleBrain.load",
                        Mock(side_effect=AssertionError("Needle must not load")))
    monkeypatch.setattr("offline_assistant.main.NativeNeedleClient",
                        Mock(side_effect=AssertionError("Needle must not load")))
    main(["call mom", "--needle-bin", "missing", "--execute-mock"])
    assert platform.called_numbers == ["5551234"]


def test_recorded_literal_call_skips_needle(monkeypatch):
    platform = DesktopPlatform([Contact("Mom", "5551234")])
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    monkeypatch.setattr("offline_assistant.main.NeedleBrain.load",
                        Mock(side_effect=AssertionError("Needle must not load")))
    voice = Mock(transcribe=Mock(return_value="call mom"))
    main(["--record", "--language", "en", "--execute-mock"], transcriber=voice)
    assert platform.called_numbers == ["5551234"]


def test_recorded_call_uses_same_validation(monkeypatch):
    platform = DesktopPlatform([Contact("Mom", "555-1234")])
    monkeypatch.setattr("offline_assistant.main.create_platform", lambda: platform)
    voice = Mock(transcribe=Mock(return_value="call mom"))
    brain = Mock(propose=Mock(return_value=[ToolCall("call_contact", {"name": "Mom"})]))
    main(["--record", "--language", "en", "--execute-mock"],
         brain=brain, transcriber=voice)
    brain.propose.assert_called_once_with("call mom")
    assert platform.called_numbers == ["5551234"]


@pytest.mark.parametrize("contacts, message", [
    ([], "Contact not found"),
    ([Contact("Mom Smith", "5551234")], "Contact not found"),
    ([Contact("Mom", "5551234"), Contact("mom", "5555678")], "Multiple numbers"),
    ([Contact("Mom", "555x1234")], "invalid phone number"),
])
def test_lookup_failures_never_call(contacts, message):
    platform = DesktopPlatform(contacts)
    with pytest.raises(ValueError, match=message):
        call_contact(platform, "Mom")
    assert platform.called_numbers == []


@pytest.mark.parametrize("number", ["", "+", "12", "123x", "123#", "++123", "1;2"])
def test_bad_number_is_rejected(number):
    with pytest.raises(ValueError):
        normalize_number(number)


def test_duplicate_contact_with_same_number_is_unambiguous():
    platform = DesktopPlatform([Contact("Mom", "555-1234"), Contact("mom", "555 1234")])
    call_contact(platform, "Mom")
    assert platform.called_numbers == ["5551234"]


@pytest.mark.parametrize("payload", ["not json", "{}", '[{"name":"Mom"}]', '[42]'])
def test_android_invalid_contact_output_fails(payload, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, payload, ""))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ValueError):
        AndroidPlatform().list_contacts()
    run.assert_called_once_with(["termux-contact-list"], check=True, timeout=15,
                                capture_output=True, text=True)


def test_android_lists_contacts_and_calls_with_literal_number(monkeypatch):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[0] == "termux-contact-list":
            return subprocess.CompletedProcess(args, 0,
                json.dumps([{"name": "Mom", "number": "+53 5555 1234"}]), "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    call_contact(AndroidPlatform(), "mom")
    assert commands == [["termux-contact-list"], ["termux-telephony-call", "+5355551234"]]


@pytest.mark.parametrize("execute", [False, True])
def test_android_cli_requires_execute_for_contact_call(monkeypatch, execute):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[0] == "termux-contact-list":
            return subprocess.CompletedProcess(args, 0, '[{"name":"Mom","number":"5551234"}]', "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    main(["call mom", "--platform", "android", "--needle-bin", "missing"] +
         (["--execute"] if execute else []))
    assert commands == ([
        ["termux-contact-list"], ["termux-telephony-call", "5551234"]
    ] if execute else [])


def test_android_contact_lookup_failure_does_not_dial(monkeypatch):
    run = Mock(side_effect=subprocess.CalledProcessError(1, "termux-contact-list"))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        call_contact(AndroidPlatform(), "Mom")
    assert run.call_count == 1


def test_android_call_failure_propagates(monkeypatch):
    def run(args, **kwargs):
        if args[0] == "termux-contact-list":
            return subprocess.CompletedProcess(args, 0, '[{"name":"Mom","number":"5551234"}]', "")
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        call_contact(AndroidPlatform(), "Mom")
