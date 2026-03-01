from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

_MODEL: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    global _MODEL
    if _MODEL is None:
        # Good default balance for speed/quality; change to "base" for faster, "medium" for better.
        _MODEL = WhisperModel("small", device="cpu", compute_type="int8")
    return _MODEL


def transcribe_wav(wav_path: Path) -> str:
    wav_path = Path(wav_path)

    model = _get_model()
    segments, _info = model.transcribe(
        str(wav_path),
        language="en",
        vad_filter=True,
        beam_size=5,
    )

    parts = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            parts.append(text)

    return " ".join(parts).strip()