from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    """A proposed action, independent of any model or platform."""

    name: str
    arguments: dict[str, object]

    @classmethod
    def from_dict(cls, value: object) -> "ToolCall":
        if not isinstance(value, dict) or set(value) != {"name", "arguments"}:
            raise ValueError("Tool calls must contain only name and arguments")
        if not isinstance(value["name"], str) or not value["name"]:
            raise ValueError("Tool name must be a nonempty string")
        if not isinstance(value["arguments"], dict):
            raise ValueError("Tool arguments must be an object")
        return cls(value["name"], dict(value["arguments"]))
