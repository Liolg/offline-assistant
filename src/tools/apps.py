"""Resolve a spoken app name to one installed Android package."""

import json
import re
import subprocess
from pathlib import Path

from platform_api.base import Platform


PACKAGE_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
KNOWN_PACKAGES = {"whatsapp": "com.whatsapp"}


def _aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read app aliases: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("App aliases must be a JSON object")
    aliases = {}
    for name, package in value.items():
        if (not isinstance(name, str) or not name.strip() or
                not isinstance(package, str) or not PACKAGE_PATTERN.fullmatch(package)):
            raise ValueError("App aliases must map names to Android package IDs")
        key = name.strip().casefold()
        if key in aliases:
            raise ValueError(f"Duplicate app alias: {name}")
        aliases[key] = package
    return aliases


def open_app(platform: Platform, name: str, aliases_path: Path = Path("apps.json")) -> str:
    """Launch a uniquely matched installed app; never guess between packages."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("App name must be a nonempty string")
    requested = name.strip().casefold()
    aliases = _aliases(aliases_path)
    if requested in aliases:
        matches = {aliases[requested]}
    elif requested in KNOWN_PACKAGES:
        matches = {KNOWN_PACKAGES[requested]}
    else:
        try:
            packages = platform.installed_packages()
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                "Cannot list installed apps on this phone. Add the app name and "
                "package ID to apps.json to open it without package discovery"
            ) from exc
        if any(not isinstance(package, str) or not PACKAGE_PATTERN.fullmatch(package)
               for package in packages):
            raise ValueError("Android returned an invalid package identifier")
        installed = set(packages)
        tokens = set(re.findall(r"[a-z0-9_]+", requested))
        matches = {package for package in installed if package.casefold() == requested}
        if not matches and len(tokens) == 1:
            matches = {package for package in installed
                       if package.casefold().split(".")[-1] == requested}
        if not matches and tokens:
            matches = {package for package in installed
                       if tokens <= set(package.casefold().split("."))}
    if not matches:
        raise ValueError(f"App not found: {name.strip()}. Add an alias to apps.json if needed")
    if len(matches) != 1:
        raise ValueError(f"Multiple apps match: {name.strip()}. Add an alias to apps.json")
    package = next(iter(matches))
    print(f"Opening {name.strip()} ({package})...", flush=True)
    platform.open_app(package)
    return package
