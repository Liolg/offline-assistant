from unittest.mock import Mock

import pytest

from assistant.brain import NeedleBrain
from assistant.tool_calls import ToolCall


def response(**overrides):
    return {
        "success": True, "type": "call", "confidence": 0.95,
        "function_calls": [{"name": "flashlight", "arguments": {"enabled": True}}],
        **overrides,
    }


def test_manual_inference_returns_data_only():
    client = Mock()
    client.complete.return_value = response()
    assert NeedleBrain(client).propose("turn on the flashlight") == [
        ToolCall("flashlight", {"enabled": True})
    ]
    client.reset.assert_called_once_with()
    client.complete.assert_called_once_with("turn on the flashlight")
    client.run.assert_not_called()


@pytest.mark.parametrize("value", [
    None, {}, response(success=False), response(type="unknown"), response(type=[]),
    response(function_calls="bad"), response(type="respond"),
    response(confidence=None), response(confidence=True),
    response(confidence=0.79), response(confidence=float("nan")),
    response(confidence=1.1), response(function_calls=[{}]),
    response(function_calls=[{"name": "flashlight", "arguments": "bad"}]),
])
def test_bad_responses_are_rejected(value):
    client = Mock()
    client.complete.return_value = value
    with pytest.raises(ValueError):
        NeedleBrain(client).propose("flashlight on")
    client.run.assert_not_called()


def test_no_matching_tool():
    client = Mock()
    client.complete.return_value = response(function_calls=[], confidence=0)
    assert NeedleBrain(client).propose("tell me a joke") == []


def test_blank_command_never_reaches_model():
    client = Mock()
    with pytest.raises(ValueError):
        NeedleBrain(client).propose("  ")
    client.complete.assert_not_called()


def test_loading_uses_schemas_and_forces_offline(monkeypatch):
    import os
    import sys
    from types import SimpleNamespace

    from assistant.brain import FLASHLIGHT_SCHEMA

    client = Mock()

    def construct(**kwargs):
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        assert os.environ["NEEDLE_TELEMETRY"] == "0"
        assert kwargs == {"tools": [FLASHLIGHT_SCHEMA]}
        return client

    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("NEEDLE_TELEMETRY", "1")
    monkeypatch.setitem(sys.modules, "needle", SimpleNamespace(Needle=construct))
    assert NeedleBrain.load().client is client


def test_missing_optional_dependency_has_setup_error(monkeypatch):
    import sys

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("NEEDLE_TELEMETRY", "0")
    monkeypatch.setitem(sys.modules, "needle", None)
    with pytest.raises(RuntimeError, match="Install the needle extra"):
        NeedleBrain.load()
