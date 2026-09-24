from dataclasses import dataclass
import re


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


def direct_open_app(text: str) -> ToolCall | None:
    """Recognize a literal request to open an application."""
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].casefold() not in {"abre", "abrir", "open"}:
        return None
    name = parts[1].strip().removesuffix(".").strip()
    for prefix in ("la aplicación ", "la aplicacion ", "la app ", "app "):
        if name.casefold().startswith(prefix):
            name = name[len(prefix):].strip()
            break
    if not name:
        return None
    return ToolCall("open_app", {"name": name})


SPANISH_HOURS = {
    "cero": 0, "una": 1, "uno": 1, "dos": 2, "tres": 3,
    "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
    "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciséis": 16,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuno": 21,
    "veintidós": 22, "veintidos": 22, "veintitrés": 23,
    "veintitres": 23,
}


def _alarm_time(value: str) -> tuple[int, int] | None:
    value = value.casefold().strip().rstrip(".")
    daypart = None
    for suffix, period in (
        ("de la mañana", "am"), ("de la madrugada", "am"),
        ("de la tarde", "pm"), ("de la noche", "night"),
        ("am", "am"), ("pm", "pm"),
    ):
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
            daypart = period
            break
    numeric = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?", value)
    if numeric:
        hour, minute = int(numeric[1]), int(numeric[2] or 0)
    else:
        words = re.fullmatch(r"([a-záéíóú]+)(?:\s+(?:y\s+)?([a-záéíóú]+))?", value)
        if not words or words[1] not in SPANISH_HOURS:
            return None
        hour = SPANISH_HOURS[words[1]]
        minute_words = {None: 0, "media": 30, "cuarto": 15,
                        "quince": 15, "treinta": 30}
        if words[2] not in minute_words:
            return None
        minute = minute_words[words[2]]
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    if daypart:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if daypart in {"pm", "night"} and hour != 12 else 0)
        if daypart == "pm" and hour == 0:
            hour = 12
    return hour, minute


def direct_set_alarm(text: str) -> ToolCall | None:
    """Recognize common Spanish alarm requests with an explicit time."""
    # Vosk has transcribed spoken "pon una alarma" as "con una alarma".
    match = re.fullmatch(
        r"(?:pon|con|poner|configura|configurar|programa|programar)\s+"
        r"(?:(?:una|la)\s+)?alarma\s+(?:a|para)\s+las?\s+(.+)",
        text.strip(), flags=re.IGNORECASE,
    )
    if match is None:
        return None
    time = _alarm_time(match[1])
    if time is None:
        raise ValueError("Unrecognized or invalid alarm time; use a time such as 7:30 or siete y media")
    return ToolCall("set_alarm", {"hour": time[0], "minute": time[1]})
