from assistant.config import create_platform
from offline_assistant.main import main
from platform_api.desktop import DesktopPlatform


def test_demo_stays_mocked_in_termux(monkeypatch, capsys):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")

    def unexpected_command(*args, **kwargs):
        raise AssertionError("The demo must not execute system commands")

    monkeypatch.setattr("subprocess.run", unexpected_command)
    assert isinstance(create_platform(), DesktopPlatform)
    main()
    assert capsys.readouterr().out == (
        "[MOCK] flashlight: on\n[MOCK] flashlight: off\n"
    )
