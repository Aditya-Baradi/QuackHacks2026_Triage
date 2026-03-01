import subprocess
from pathlib import Path


def convert_webm_to_wav(webm_path: Path, wav_path: Path) -> None:
    """
    Convert .webm -> .wav using ffmpeg.
    Requires ffmpeg installed and available on PATH.
    """
    webm_path = Path(webm_path)
    wav_path = Path(wav_path)

    if not webm_path.exists():
        raise FileNotFoundError(f"Input file not found: {webm_path}")

    wav_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(webm_path),
        "-ac", "1",
        "-ar", "16000",
        str(wav_path),
    ]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg to support .webm input."
        ) from e

    if p.returncode != 0:
        raise RuntimeError(
            "ffmpeg conversion failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stderr:\n{p.stderr}"
        )