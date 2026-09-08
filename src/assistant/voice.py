import json
from pathlib import Path
from typing import Protocol
import wave


MODEL_DIRECTORIES = {
    "en": "vosk-model-small-en-us-0.15",
    "es": "vosk-model-small-es-0.42",
}


class Transcriber(Protocol):
    def transcribe(self, audio_path: str, language: str) -> str:
        """Return text from a local recording without selecting or executing tools."""
        ...


class VoskTranscriber:
    """Transcribe a mono, 16-bit, 16 kHz PCM WAV with a local language model."""

    def __init__(self, models_dir: str = "models") -> None:
        self.models_dir = Path(models_dir).expanduser()

    def transcribe(self, audio_path: str, language: str) -> str:
        if language not in MODEL_DIRECTORIES:
            raise ValueError("Choose language en or es")
        try:
            with wave.open(str(Path(audio_path).expanduser()), "rb") as recording:
                if (
                    recording.getnchannels() != 1
                    or recording.getsampwidth() != 2
                    or recording.getframerate() != 16000
                    or recording.getcomptype() != "NONE"
                ):
                    raise ValueError("Audio must be a mono, 16-bit, 16000 Hz PCM WAV")
                if recording.getnframes() == 0:
                    raise ValueError("Audio recording is empty")
                model_path = self.models_dir / MODEL_DIRECTORIES[language]
                if not model_path.is_dir():
                    raise ValueError(f"Missing local Vosk model: {model_path}. See README.md")
                try:
                    from vosk import KaldiRecognizer, Model
                except (ImportError, OSError) as exc:
                    raise RuntimeError(
                        "Vosk could not be imported. Install the voice extra on a "
                        "supported platform; native Termux requires separate verification."
                    ) from exc
                try:
                    # An explicit path prevents Vosk's language-based auto-download.
                    model = Model(model_path=str(model_path))
                    recognizer = KaldiRecognizer(model, recording.getframerate())
                except Exception as exc:
                    raise RuntimeError(f"Could not load Vosk model: {model_path}") from exc
                parts = []
                bytes_read = 0
                while data := recording.readframes(4000):
                    bytes_read += len(data)
                    if recognizer.AcceptWaveform(data):
                        parts.append(self._text(recognizer.Result()))
                if bytes_read != recording.getnframes() * 2:
                    raise ValueError("Audio recording is truncated")
                parts.append(self._text(recognizer.FinalResult()))
                return " ".join(part for part in parts if part)
        except (wave.Error, EOFError) as exc:
            raise ValueError("Cannot read audio; provide a mono, 16-bit, 16000 Hz PCM WAV") from exc

    @staticmethod
    def _text(result: str) -> str:
        try:
            value = json.loads(result)
        except json.JSONDecodeError as exc:
            raise ValueError("Vosk returned invalid JSON") from exc
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            raise ValueError("Vosk returned an invalid transcript")
        return value["text"].strip()
