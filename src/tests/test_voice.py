import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import wave

import pytest

from assistant.voice import MODEL_DIRECTORIES, VoskTranscriber


def make_wav(path, *, channels=1, width=2, rate=16000, frames=8001):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(width)
        audio.setframerate(rate)
        audio.writeframes(b"\x00" * frames * width * channels)
    return str(path)


@pytest.mark.parametrize("language, words", [
    ("en", ["turn on", "the flashlight", "please"]),
    ("es", ["enciende", "la linterna", "por favor"]),
])
def test_language_selection_and_all_finalized_segments(tmp_path, monkeypatch, language, words):
    model_path = tmp_path / MODEL_DIRECTORIES[language]
    model_path.mkdir()
    audio = make_wav(tmp_path / "command.wav")
    recognizer = Mock()
    recognizer.AcceptWaveform.side_effect = [True, True, False]
    recognizer.Result.side_effect = [json.dumps({"text": part}) for part in words[:2]]
    recognizer.FinalResult.return_value = json.dumps({"text": words[2]})
    sdk = SimpleNamespace(Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer))
    monkeypatch.setitem(sys.modules, "vosk", sdk)
    assert VoskTranscriber(str(tmp_path)).transcribe(audio, language) == " ".join(words)
    sdk.Model.assert_called_once_with(model_path=str(model_path))
    sdk.KaldiRecognizer.assert_called_once_with(sdk.Model.return_value, 16000)
    assert [len(call.args[0]) for call in recognizer.AcceptWaveform.call_args_list] == [8000, 8000, 2]


@pytest.mark.parametrize("options", [{"channels": 2}, {"width": 1}, {"rate": 44100}])
def test_wrong_format_rejected_before_loading_model(tmp_path, options):
    audio = make_wav(tmp_path / "bad.wav", **options)
    with pytest.raises(ValueError, match="mono, 16-bit, 16000 Hz"):
        VoskTranscriber().transcribe(audio, "en")


def test_empty_audio(tmp_path):
    audio = make_wav(tmp_path / "empty.wav", frames=0)
    with pytest.raises(ValueError, match="empty"):
        VoskTranscriber().transcribe(audio, "es")


def test_missing_model_never_uses_sdk_download(tmp_path, monkeypatch):
    sdk = Mock()
    monkeypatch.setitem(sys.modules, "vosk", sdk)
    audio = make_wav(tmp_path / "command.wav")
    with pytest.raises(ValueError, match="Missing local Vosk model"):
        VoskTranscriber(str(tmp_path)).transcribe(audio, "en")
    sdk.Model.assert_not_called()


def test_missing_sdk_has_actionable_error(tmp_path, monkeypatch):
    (tmp_path / MODEL_DIRECTORIES["en"]).mkdir()
    audio = make_wav(tmp_path / "command.wav")
    monkeypatch.setitem(sys.modules, "vosk", None)
    with pytest.raises(RuntimeError, match="voice extra"):
        VoskTranscriber(str(tmp_path)).transcribe(audio, "en")


def test_invalid_wav(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_text("not a recording")
    with pytest.raises(ValueError, match="Cannot read audio"):
        VoskTranscriber().transcribe(str(path), "en")


@pytest.mark.parametrize("result", ['{}', '[]', '{"text": 3}', 'invalid'])
def test_invalid_recognition_result(result):
    with pytest.raises(ValueError):
        VoskTranscriber._text(result)


def test_truncated_audio_is_rejected(tmp_path, monkeypatch):
    (tmp_path / MODEL_DIRECTORIES["en"]).mkdir()
    audio = tmp_path / "truncated.wav"
    make_wav(audio)
    audio.write_bytes(audio.read_bytes()[:-4])
    recognizer = Mock()
    recognizer.AcceptWaveform.return_value = False
    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(
        Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer)))
    with pytest.raises(ValueError, match="truncated"):
        VoskTranscriber(str(tmp_path)).transcribe(str(audio), "en")
    recognizer.FinalResult.assert_not_called()


def test_silence_produces_empty_transcript(tmp_path, monkeypatch):
    (tmp_path / MODEL_DIRECTORIES["es"]).mkdir()
    audio = make_wav(tmp_path / "silence.wav")
    recognizer = Mock()
    recognizer.AcceptWaveform.return_value = False
    recognizer.FinalResult.return_value = '{"text": ""}'
    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(
        Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer)))
    assert VoskTranscriber(str(tmp_path)).transcribe(audio, "es") == ""


def test_unsupported_language():
    with pytest.raises(ValueError, match="en or es"):
        VoskTranscriber().transcribe("command.wav", "fr")
