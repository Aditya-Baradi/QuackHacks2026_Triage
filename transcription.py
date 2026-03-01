from pathlib import Path

from openai import OpenAI

from ..config import OPENAI_API_KEY


def transcribe_wav(path: str | Path) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    wav_path = Path(path)
    client = OpenAI(api_key=OPENAI_API_KEY)

    with wav_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text")

    transcript = (text or "").strip()
    if not transcript:
        raise RuntimeError("Whisper returned empty transcript")

    return transcript
