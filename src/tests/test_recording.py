import json
from pathlib import Path
from unittest.mock import Mock
import subprocess
import wave

import pytest

from assistant.tool_calls import ToolCall
from offline_assistant.main import main
from platform_api.android import AndroidPlatform
from platform_api.desktop import DesktopPlatform


def test_desktop_records_valid_silence_without_processes(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', Mock(side_effect=AssertionError('hardware access')))
    target = tmp_path / 'command.wav'
    DesktopPlatform().record_audio(target, 2)
    with wave.open(str(target)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        assert audio.getnframes() == 32000
        assert not any(audio.readframes(32000))


@pytest.mark.parametrize('seconds', [0, 31, True, 1.5])
@pytest.mark.parametrize('platform', [DesktopPlatform, AndroidPlatform])
def test_invalid_duration_fails_before_recording(tmp_path, seconds, platform):
    with pytest.raises(ValueError):
        platform().record_audio(tmp_path / 'out.wav', seconds)


@pytest.mark.parametrize('execute', [False, True])
def test_record_flow_previews_or_executes_and_removes_audio(monkeypatch, execute):
    platform = DesktopPlatform()
    monkeypatch.setattr('offline_assistant.main.create_platform', lambda: platform)
    paths = []
    def transcribe(path, language):
        assert Path(path).is_file()
        assert language == 'es'
        paths.append(Path(path))
        return 'enciende la linterna'
    voice = Mock(transcribe=transcribe)
    brain = Mock()
    brain.propose.return_value = [ToolCall('flashlight', {'enabled': True})]
    main(['--record', '--language', 'es'] + (['--execute'] if execute else []),
         brain=brain, transcriber=voice)
    brain.propose.assert_called_once_with('enciende la linterna')
    assert platform.flashlight_enabled is execute
    assert not paths[0].exists()


@pytest.mark.parametrize('failure', [RuntimeError('permission denied'), KeyboardInterrupt()])
def test_record_failure_does_not_transcribe_or_execute(monkeypatch, failure):
    platform = Mock()
    platform.record_audio.side_effect = failure
    monkeypatch.setattr('platform_api.android.AndroidPlatform', lambda: platform)
    voice, brain = Mock(), Mock()
    with pytest.raises(SystemExit):
        main(['--record', '--language', 'en', '--platform', 'android', '--execute'],
             brain=brain, transcriber=voice)
    voice.transcribe.assert_not_called()
    brain.propose.assert_not_called()
    platform.flashlight.assert_not_called()


def test_record_transcribe_only_on_android(monkeypatch):
    platform = Mock()
    monkeypatch.setattr('platform_api.android.AndroidPlatform', lambda: platform)
    voice, brain = Mock(), Mock()
    voice.transcribe.return_value = 'hello'
    main(['--record', '--language', 'en', '--platform', 'android', '--transcribe-only'],
         brain=brain, transcriber=voice)
    platform.record_audio.assert_called_once()
    brain.propose.assert_not_called()
    platform.flashlight.assert_not_called()


@pytest.mark.parametrize('args', [
    ['--record'], ['hello', '--record', '--language', 'en'],
    ['--audio', 'a.wav', '--record', '--language', 'en'],
    ['--seconds', '8'], ['--record', '--language', 'en', '--seconds', '0'],
    ['--record', '--language', 'en', '--seconds', '31'],
])
def test_invalid_record_options(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


@pytest.mark.parametrize('mode', ['success', 'busy', 'denied', 'timeout', 'interrupt', 'conversion'])
def test_android_capture_waits_converts_and_handles_failures(tmp_path, monkeypatch, mode):
    commands = []
    source = None
    status_calls = 0
    def run(args, **kwargs):
        nonlocal source, status_calls
        commands.append(args)
        if args[0] == 'ffmpeg':
            assert source.exists()
            assert args[args.index('-ar') + 1] == '16000'
            Path(args[-1]).write_bytes(b'converted')
            return subprocess.CompletedProcess(args, int(mode == 'conversion'), '', 'conversion error')
        if args[1] == '-i':
            status_calls += 1
            active = mode == 'busy' or (source is not None and mode != 'denied' and
                     (status_calls == 2 or mode in ('timeout', 'interrupt')))
            result = json.dumps({'isRecording': active, 'outputFile': str(source)})
        elif args[1] == '-f':
            source = Path(args[2])
            source.write_bytes(b'aac')
            result = 'permission denied' if mode == 'denied' else f'Recording started: {source}'
        else:
            result = 'Recording finished'
        return subprocess.CompletedProcess(args, 0, result, '')
    def sleep(seconds):
        if mode == 'interrupt':
            raise KeyboardInterrupt()
    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.setattr('platform_api.android.time.sleep', sleep)
    if mode == 'success':
        AndroidPlatform().record_audio(tmp_path / 'out.wav', 8)
        assert (tmp_path / 'out.wav').read_bytes() == b'converted'
    else:
        with pytest.raises(KeyboardInterrupt if mode == 'interrupt' else RuntimeError):
            AndroidPlatform().record_audio(tmp_path / 'out.wav', 8)
    assert any(c[0] == 'ffmpeg' for c in commands) is (mode in ('success', 'conversion'))
    assert (['termux-microphone-record', '-q'] in commands) is (mode in ('timeout', 'interrupt'))
    if source is not None:
        assert not source.exists()
