from assistant.tool_calls import ToolCall
from platform_api.base import Platform
from tools.alarms import set_alarm
from tools.apps import open_app
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
        elif call.name == "open_app":
            if set(call.arguments) != {"name"}:
                raise ValueError("open_app requires exactly one argument: name")
            if not isinstance(call.arguments["name"], str) or not call.arguments["name"].strip():
                raise ValueError("name must be a nonempty string")
        elif call.name == "set_alarm":
            if set(call.arguments) != {"hour", "minute"}:
                raise ValueError("set_alarm requires hour and minute")
            if type(call.arguments["hour"]) is not int or not 0 <= call.arguments["hour"] <= 23:
                raise ValueError("Alarm hour must be an integer from 0 to 23")
            if type(call.arguments["minute"]) is not int or not 0 <= call.arguments["minute"] <= 59:
                raise ValueError("Alarm minute must be an integer from 0 to 59")
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
        elif call.name == "call_contact":
            call_contact(self.platform, call.arguments["name"])
        elif call.name == "open_app":
            open_app(self.platform, call.arguments["name"])
        else:
            set_alarm(self.platform, call.arguments["hour"], call.arguments["minute"])
