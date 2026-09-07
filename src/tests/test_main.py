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
