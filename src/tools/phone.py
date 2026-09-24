"""Device-independent contact lookup and validated phone calls."""

import re

from platform_api.base import Contact, Platform


MOTHER_NAMES = {"mamá", "mama", "mi mamá", "mi mama"}


def normalize_number(number: str) -> str:
    """Remove display separators while retaining the dialing prefix."""
    if not isinstance(number, str) or not number.strip():
        raise ValueError("Contact has no phone number")
    if re.search(r"[^+0-9\s().-]", number):
        raise ValueError("Contact has an invalid phone number")
    normalized = re.sub(r"[\s().-]", "", number)
    if not re.fullmatch(r"\+?[0-9]{3,15}", normalized):
        raise ValueError("Contact has an invalid phone number")
    return normalized


def call_contact(platform: Platform, name: str) -> Contact:
    """Call one exact contact, refusing missing or ambiguous matches."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Contact name must be a nonempty string")
    requested = name.strip().casefold()
    contacts = platform.list_contacts()

    def matching_contacts(names: set[str]) -> dict[str, Contact]:
        matches: dict[str, Contact] = {}
        for contact in contacts:
            if contact.name.strip().casefold() in names:
                number = normalize_number(contact.number)
                matches[number] = Contact(contact.name.strip(), number)
        return matches

    matches = matching_contacts({requested})
    # Vosk may omit the accent in mamá. Prefer an actual Spanish contact name.
    if not matches and requested in MOTHER_NAMES:
        matches = matching_contacts(MOTHER_NAMES - {requested})
        if not matches:
            matches = matching_contacts({"mom"})
    if not matches:
        raise ValueError(f"Contact not found: {name.strip()}")
    if len(matches) != 1:
        raise ValueError(f"Multiple numbers found for contact: {name.strip()}")
    contact = next(iter(matches.values()))
    print(f"Calling {contact.name} ({contact.number})...", flush=True)
    platform.call_phone(contact.number)
    return contact
