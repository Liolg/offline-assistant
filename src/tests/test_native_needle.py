import json
from pathlib import Path
import subprocess

import pytest

from assistant.brain import FLASHLIGHT_SCHEMA, NeedleBrain
from assistant.native_needle import NativeNeedleClient
from assistant.tool_calls import ToolCall


def test_native_request_uses_current_schema_and_literal_arguments(monkeypatch, tmp_path):
    executable = tmp_path / "needle binary"
    prompt = 'turn on flashlight; $(touch unwanted)'
    schema_paths = []

    def run(args, **kwargs):
        assert args[0] == str(executable)
        assert args[3:] == ["--prompt", prompt]
        assert kwargs["timeout"] == 30
        assert kwargs["check"] is True
        assert kwargs["env"]["NEEDLE_TELEMETRY"] == "0"
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert not kwargs.get("shell", False)
        schema = Path(args[2])
        schema_paths.append(schema)
        assert json.loads(schema.read_text()) == [FLASHLIGHT_SCHEMA]
        return subprocess.CompletedProcess(args, 0, json.dumps({
            "type": "call", "success": True, "confidence": 1.0,
            "function_calls": [{"name": "flashlight", "arguments": {"enabled": True}}],
        }))

    monkeypatch.setattr("assistant.native_needle.subprocess.run", run)
    brain = NeedleBrain(NativeNeedleClient(str(executable)))
    assert brain.propose(prompt) == [ToolCall("flashlight", {"enabled": True})]
    assert not schema_paths[0].exists()


@pytest.mark.parametrize("failure, message", [
    (subprocess.TimeoutExpired("needle", 30), "timed out"),
    (subprocess.CalledProcessError(2, "needle", stderr="bad engine"), "bad engine"),
])
def test_process_errors_clean_up_schema(monkeypatch, failure, message):
    paths = []

    def run(args, **kwargs):
        paths.append(Path(args[2]))
        raise failure

    monkeypatch.setattr("assistant.native_needle.subprocess.run", run)
    with pytest.raises(RuntimeError, match=message):
        NativeNeedleClient("needle").complete("on")
    assert not paths[0].exists()


def test_invalid_json(monkeypatch):
    monkeypatch.setattr("assistant.native_needle.subprocess.run", lambda *a, **kw:
                        subprocess.CompletedProcess([], 0, "not JSON"))
    with pytest.raises(ValueError, match="invalid JSON"):
        NativeNeedleClient("needle").complete("on")
