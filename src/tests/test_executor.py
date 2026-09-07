from unittest.mock import Mock

import pytest

from assistant.executor import Executor
from assistant.tool_calls import ToolCall
from platform_api.base import Platform


@pytest.mark.parametrize("enabled", [True, False])
def test_dispatch(enabled):
    platform = Mock(spec=Platform)
    Executor(platform).execute(ToolCall("flashlight", {"enabled": enabled}))
    platform.flashlight.assert_called_once_with(enabled)


@pytest.mark.parametrize("call", [
    ToolCall("call_contact", {"name": "Alice"}),
    ToolCall("__import__", {}),
    ToolCall("flashlight", {}),
    ToolCall("flashlight", {"enabled": True, "extra": 1}),
    ToolCall("flashlight", {"enabled": "false"}),
    ToolCall("flashlight", {"enabled": 1}),
])
def test_invalid_call_has_no_side_effects(call):
    platform = Mock(spec=Platform)
    with pytest.raises(ValueError):
        Executor(platform).execute(call)
    platform.flashlight.assert_not_called()


def test_device_error_propagates():
    platform = Mock(spec=Platform)
    platform.flashlight.side_effect = OSError("unavailable")
    with pytest.raises(OSError, match="unavailable"):
        Executor(platform).execute(ToolCall("flashlight", {"enabled": True}))
