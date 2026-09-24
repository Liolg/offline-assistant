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


def direct_contact_call(text: str) -> ToolCall | None:
    """Recognize literal English and Spanish contact-call commands."""
    parts = text.strip().split(maxsplit=2)
    if len(parts) >= 2 and parts[0].casefold() == "call":
        name = " ".join(parts[1:])
    elif len(parts) >= 2 and parts[0].casefold() in {"llama", "llamar"}:
        if parts[1].casefold() == "a":
            if len(parts) != 3:
                return None
            name = parts[2]
        else:
            name = " ".join(parts[1:])
    else:
        return None
    name = name.strip()
    if name.endswith("."):
        name = name[:-1].rstrip()
    if not name:
        return None
    return ToolCall("call_contact", {"name": name})
