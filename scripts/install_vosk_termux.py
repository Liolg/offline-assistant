"""Build and install Vosk 0.3.45 bindings with the official Android ARM64 library."""

import base64
import csv
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import URLError
from urllib.request import urlopen
from http.client import HTTPException
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile


VERSION = "0.3.45"
RELEASE = f"https://github.com/alphacep/vosk-api/releases/download/v{VERSION}"
PYTHON_WHEEL = f"vosk-{VERSION}-py3-none-manylinux2014_aarch64.whl"
ANDROID_ARCHIVE = f"vosk-android-{VERSION}.zip"
DIST_INFO = f"vosk-{VERSION}.dist-info"


def validate_archive(path: Path) -> None:
    """Reject incomplete archives before caching or installing them."""
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise BadZipFile("Archive checksum failed")


def download_release(filename: str, cache: Path) -> Path:
    """Retry interrupted transfers and reuse verified, completed downloads."""
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / filename
    if target.exists():
        try:
            validate_archive(target)
        except (BadZipFile, EOFError):
            target.unlink()
        else:
            print(f"Using cached release: {filename}", flush=True)
            return target
    partial = target.with_name(target.name + ".part")
    for attempt in range(1, 4):
        print(f"Downloading official Vosk release ({attempt}/3): {filename}", flush=True)
        try:
            with urlopen(f"{RELEASE}/{filename}", timeout=30) as response:
                with partial.open("wb") as destination:
                    shutil.copyfileobj(response, destination)
            validate_archive(partial)
            partial.replace(target)
            return target
        except (OSError, URLError, HTTPException, BadZipFile, EOFError) as error:
            if attempt == 3:
                raise SystemExit(
                    f"Download failed: {filename}: {error}\n"
                    "Check your connection and rerun this command. "
                    f"Completed downloads are kept in {cache}."
                ) from error
            print(f"Download interrupted: {error}. Retrying...", flush=True)
            time.sleep(attempt * 2)
        finally:
            partial.unlink(missing_ok=True)
    raise AssertionError("Unreachable")


def build_wheel(python_wheel: Path, android_archive: Path, output: Path, tag: str) -> Path:
    """Replace the Linux library, retag the wheel, and regenerate its RECORD."""
    if not re.fullmatch(r"py3-none-[a-zA-Z0-9_]+", tag):
        raise ValueError("Invalid wheel tag")
    with ZipFile(python_wheel) as source:
        files = {item.filename: source.read(item) for item in source.infolist() if not item.is_dir()}
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe wheel path")
    if "vosk/libvosk.so" not in files or f"{DIST_INFO}/WHEEL" not in files:
        raise ValueError("Unexpected Python wheel layout")
    with ZipFile(android_archive) as source:
        libraries = [name for name in source.namelist()
                     if PurePosixPath(name).parts[-2:] == ("arm64-v8a", "libvosk.so")]
        if len(libraries) != 1:
            raise ValueError("Expected one Android arm64-v8a/libvosk.so")
        native = source.read(libraries[0])
    if native[:6] != b"\x7fELF\x02\x01" or int.from_bytes(native[18:20], "little") != 183:
        raise ValueError("Android library is not a little-endian ARM64 ELF binary")
    files["vosk/libvosk.so"] = native
    metadata = files[f"{DIST_INFO}/WHEEL"].decode("utf-8")
    lines = [line for line in metadata.splitlines() if not line.startswith("Tag:")]
    files[f"{DIST_INFO}/WHEEL"] = ("\n".join(lines) + f"\nTag: {tag}\n").encode()
    record = f"{DIST_INFO}/RECORD"
    files.pop(record, None)
    rows = io.StringIO(newline="")
    writer = csv.writer(rows)
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow([name, f"sha256={digest}", len(data)])
    writer.writerow([record, "", ""])
    files[record] = rows.getvalue().encode()
    output.mkdir(parents=True, exist_ok=True)
    wheel = output / f"vosk-{VERSION}-{tag}.whl"
    with ZipFile(wheel, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return wheel


def main() -> None:
    if "com.termux" not in os.environ.get("PREFIX", "") or platform.machine() != "aarch64":
        raise SystemExit("Run this helper inside native ARM64 Termux on your phone.")
    if sys.prefix == sys.base_prefix:
        raise SystemExit("Activate a virtual environment first; see README.md.")
    try:
        from packaging.tags import sys_tags
    except ImportError:
        raise SystemExit("Install packaging first: python -m pip install packaging")
    supported = list(sys_tags())
    tag = next((str(item) for item in supported if item.interpreter == "py3" and item.abi == "none"
                and item.platform != "any" and "manylinux" not in item.platform
                and "musllinux" not in item.platform), None)
    if tag is None:
        raise SystemExit("Could not determine the native Termux wheel tag.")
    cache = Path.home() / ".cache" / "offline-assistant" / "vosk" / VERSION
    python_wheel = download_release(PYTHON_WHEEL, cache)
    android_archive = download_release(ANDROID_ARCHIVE, cache)
    with TemporaryDirectory(prefix="vosk-termux-") as directory:
        work = Path(directory)
        wheel = build_wheel(python_wheel, android_archive, work, tag)
        subprocess.run([sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel)], check=True)
        subprocess.run([sys.executable, "-c", "import vosk; print('Vosk import OK')"], check=True)
    print("Runtime installed. English and Spanish models are separate downloads.")


if __name__ == "__main__":
    main()
