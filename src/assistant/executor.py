from assistant.tool_calls import ToolCall
from platform_api.base import Platform
from tools.system import flashlight


class Executor:
    """Validate proposals against an explicit allowlist before dispatch."""

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    def validate(self, call: ToolCall) -> None:
        if call.name != "flashlight":
            raise ValueError(f"Unsupported tool: {call.name}")
        if set(call.arguments) != {"enabled"}:
            raise ValueError("flashlight requires exactly one argument: enabled")
        if not isinstance(call.arguments["enabled"], bool):
            raise ValueError("enabled must be a bool")

    def execute(self, call: ToolCall) -> None:
        self.validate(call)
        flashlight(self.platform, call.arguments["enabled"])
