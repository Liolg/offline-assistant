import base64
import csv
import hashlib
import importlib.util
import io
from pathlib import Path
from zipfile import ZipFile

import pytest


spec = importlib.util.spec_from_file_location(
    "install_vosk_termux", Path(__file__).resolve().parents[2] / "scripts/install_vosk_termux.py"
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def archives(tmp_path, *, native=None, name="arm64-v8a/libvosk.so"):
    wheel, android = tmp_path / "bindings.whl", tmp_path / "android.zip"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("vosk/libvosk.so", b"linux binary")
        archive.writestr("vosk/__init__.py", "# bindings\n")
        archive.writestr(f"{setup.DIST_INFO}/WHEEL", "Wheel-Version: 1.0\nTag: py3-none-manylinux2014_aarch64\n")
        archive.writestr(f"{setup.DIST_INFO}/RECORD", "stale record")
    if native is None:
        native = b"\x7fELF\x02\x01" + bytes(12) + (183).to_bytes(2, "little")
    with ZipFile(android, "w") as archive:
        archive.writestr(name, native)
    return wheel, android, native


def test_repackages_android_library_and_recomputes_every_hash(tmp_path):
    wheel, android, native = archives(tmp_path)
    result = setup.build_wheel(wheel, android, tmp_path / "output", "py3-none-linux_aarch64")
    assert result.name == "vosk-0.3.45-py3-none-linux_aarch64.whl"
    with ZipFile(result) as archive:
        assert archive.read("vosk/libvosk.so") == native
        assert archive.read("vosk/__init__.py") == b"# bindings\n"
        metadata = archive.read(f"{setup.DIST_INFO}/WHEEL").decode()
        assert "manylinux" not in metadata
        assert "Tag: py3-none-linux_aarch64" in metadata
        rows = list(csv.reader(io.StringIO(archive.read(f"{setup.DIST_INFO}/RECORD").decode())))
        assert len(rows) == len(archive.namelist())
        for name, digest, size in rows[:-1]:
            data = archive.read(name)
            assert int(size) == len(data)
            expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            assert digest == f"sha256={expected}"
        assert rows[-1] == [f"{setup.DIST_INFO}/RECORD", "", ""]


@pytest.mark.parametrize("native", [b"", b"not an ELF", b"\x7fELF\x02\x01" + bytes(14)])
def test_rejects_incorrect_architecture(tmp_path, native):
    wheel, android, _ = archives(tmp_path, native=native)
    with pytest.raises(ValueError, match="ARM64 ELF"):
        setup.build_wheel(wheel, android, tmp_path / "out", "py3-none-linux_aarch64")


def test_rejects_unexpected_archive(tmp_path):
    wheel, android, _ = archives(tmp_path, name="x86/libvosk.so")
    with pytest.raises(ValueError, match="Expected one Android"):
        setup.build_wheel(wheel, android, tmp_path / "out", "py3-none-linux_aarch64")


def test_installer_refuses_desktop_before_downloading(monkeypatch):
    monkeypatch.setenv("PREFIX", "/usr")
    with pytest.raises(SystemExit, match="native ARM64 Termux"):
        setup.main()


def test_installer_requires_virtual_environment(monkeypatch):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr(setup.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(setup.sys, "prefix", setup.sys.base_prefix)
    with pytest.raises(SystemExit, match="virtual environment"):
        setup.main()


def test_download_retries_connection_reset_and_reuses_cache(tmp_path, monkeypatch):
    wheel, _, _ = archives(tmp_path)
    payload = wheel.read_bytes()
    requests = []

    class InterruptedResponse(io.BytesIO):
        def read(self, size=-1):
            if self.tell():
                raise ConnectionResetError(104, "Connection reset by peer")
            return super().read(10)

    def open_url(url, *, timeout):
        requests.append((url, timeout))
        if len(requests) == 1:
            return InterruptedResponse(payload)
        return io.BytesIO(payload)

    monkeypatch.setattr(setup, "urlopen", open_url)
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: None)
    cache = tmp_path / "cache"
    result = setup.download_release(setup.PYTHON_WHEEL, cache)
    assert result.read_bytes() == payload
    assert len(requests) == 2
    assert setup.download_release(setup.PYTHON_WHEEL, cache) == result
    assert len(requests) == 2
    assert not list(cache.glob("*.part"))


def test_failed_download_keeps_completed_files(tmp_path, monkeypatch):
    wheel, _, _ = archives(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    completed = cache / setup.PYTHON_WHEEL
    completed.write_bytes(wheel.read_bytes())
    requests = []

    def open_url(url, *, timeout):
        requests.append(url)
        raise TimeoutError("timed out")

    monkeypatch.setattr(setup, "urlopen", open_url)
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: None)
    with pytest.raises(SystemExit, match="Completed downloads are kept"):
        setup.download_release(setup.ANDROID_ARCHIVE, cache)
    assert len(requests) == 3
    assert completed.read_bytes() == wheel.read_bytes()
    assert not (cache / setup.ANDROID_ARCHIVE).exists()
    assert not list(cache.glob("*.part"))


def test_corrupt_cache_and_incomplete_response_are_redownloaded(tmp_path, monkeypatch):
    wheel, _, _ = archives(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / setup.PYTHON_WHEEL).write_bytes(b"broken cached archive")
    responses = iter([b"truncated transfer", wheel.read_bytes()])
    monkeypatch.setattr(setup, "urlopen", lambda url, timeout: io.BytesIO(next(responses)))
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: None)
    result = setup.download_release(setup.PYTHON_WHEEL, cache)
    assert result.read_bytes() == wheel.read_bytes()
