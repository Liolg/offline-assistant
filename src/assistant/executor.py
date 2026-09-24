from assistant.tool_calls import ToolCall
from platform_api.base import Platform
from tools.phone import call_contact
from tools.system import flashlight


class Executor:
    """Validate proposals against an explicit allowlist before dispatch."""

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    def validate(self, call: ToolCall) -> None:
        if call.name == "flashlight":
            if set(call.arguments) != {"enabled"}:
                raise ValueError("flashlight requires exactly one argument: enabled")
            if not isinstance(call.arguments["enabled"], bool):
                raise ValueError("enabled must be a bool")
        elif call.name == "call_contact":
            if set(call.arguments) != {"name"}:
                raise ValueError("call_contact requires exactly one argument: name")
            if not isinstance(call.arguments["name"], str) or not call.arguments["name"].strip():
                raise ValueError("name must be a nonempty string")
        else:
            raise ValueError(f"Unsupported tool: {call.name}")

    def validate_proposal(self, calls: list[ToolCall]) -> None:
        """Validate every call before allowing any side effect."""
        for call in calls:
            self.validate(call)
        if any(call.name == "call_contact" for call in calls) and len(calls) != 1:
            raise ValueError("A contact call must be the only proposed action")

    def execute(self, call: ToolCall) -> None:
        self.validate(call)
        if call.name == "flashlight":
            flashlight(self.platform, call.arguments["enabled"])
        else:
            call_contact(self.platform, call.arguments["name"])
