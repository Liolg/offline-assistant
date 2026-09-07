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
            return cls(Needle(tools=[FLASHLIGHT_SCHEMA]))
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
