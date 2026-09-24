import os
from typing import Protocol

from assistant.tool_calls import ToolCall


FLASHLIGHT_SCHEMA = {
    "name": "flashlight",
    "description": "Turn the device flashlight on or off.",
    "parameters": {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to turn the flashlight on, false to turn it off.",
            }
        },
        "required": ["enabled"],
        "additionalProperties": False,
    },
}

CALL_CONTACT_SCHEMA = {
    "name": "call_contact",
    "description": "Place a phone call to a contact saved on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The contact's saved name."},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}

OPEN_APP_SCHEMA = {
    "name": "open_app",
    "description": "Open an installed Android application by its spoken name.",
    "parameters": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Application name."}},
        "required": ["name"],
        "additionalProperties": False,
    },
}

SET_ALARM_SCHEMA = {
    "name": "set_alarm",
    "description": "Set a one-time alarm at a local time in 24-hour format.",
    "parameters": {
        "type": "object",
        "properties": {
            "hour": {"type": "integer", "description": "Hour from 0 to 23."},
            "minute": {"type": "integer", "description": "Minute from 0 to 59."},
        },
        "required": ["hour", "minute"],
        "additionalProperties": False,
    },
}

TOOL_SCHEMAS = [FLASHLIGHT_SCHEMA, CALL_CONTACT_SCHEMA, OPEN_APP_SCHEMA, SET_ALARM_SCHEMA]


class Brain(Protocol):
    def propose(self, text: str) -> list[ToolCall]:
        """Return proposals without executing device operations."""
        ...


class NeedleClient(Protocol):
    def reset(self) -> None: ...

    def complete(self, text: str) -> object: ...


class NeedleBrain:
    """Translate independent typed commands using Needle's manual API."""

    def __init__(self, client: NeedleClient) -> None:
        self.client = client

    @classmethod
    def load(cls) -> "NeedleBrain":
        # Set before importing the SDK so a missing engine cannot trigger a fetch.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["NEEDLE_TELEMETRY"] = "0"
        try:
            from needle import Needle
        except ImportError as exc:
            raise RuntimeError("Install the needle extra first; see README.md") from exc
        try:
            return cls(Needle(tools=TOOL_SCHEMAS))
        except Exception as exc:
            raise RuntimeError(
                "Could not load the cached Needle engine. Run the explicit setup "
                "command in README.md first."
            ) from exc

    def propose(self, text: str) -> list[ToolCall]:
        if not text.strip():
            raise ValueError("Command must not be empty")
        self.client.reset()
        response = self.client.complete(text)
        if not isinstance(response, dict) or response.get("success") is not True:
            raise ValueError("Needle did not return a successful response")
        if response.get("type") not in ("call", "respond"):
            raise ValueError("Unknown Needle response type")
        calls = response.get("function_calls")
        if not isinstance(calls, list):
            raise ValueError("Needle function_calls must be a list")
        if not calls:
            return []
        if response["type"] != "call":
            raise ValueError("Unexpected calls in a non-call response")
        confidence = response.get("confidence")
        if type(confidence) not in (int, float) or not 0.8 <= confidence <= 1.0:
            raise ValueError("Needle confidence is missing or below 0.8; rephrase the command")
        return [ToolCall.from_dict(call) for call in calls]
