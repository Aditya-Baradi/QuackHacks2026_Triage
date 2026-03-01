from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

try:
    import soundfile as sf
except Exception:
    sf = None


def _require_soundfile() -> None:
    if sf is None:
        raise RuntimeError("soundfile is required. Install with: pip install soundfile")


def _frame_rms(x: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if x.size < frame:
        x = np.pad(x, (0, frame - x.size), mode="constant")
    n_frames = 1 + (x.size - frame) // hop
    out = np.empty(n_frames, dtype=np.float64)
    for i in range(n_frames):
        s = i * hop
        seg = x[s : s + frame]
        out[i] = float(np.sqrt(np.mean(seg * seg) + 1e-12))
    return out


def _robust_voiced_mask(rms: np.ndarray) -> np.ndarray:
    if rms.size == 0:
        return np.array([], dtype=bool)

    p20 = float(np.percentile(rms, 20))
    p80 = float(np.percentile(rms, 80))
    thr = p20 + 0.25 * (p80 - p20)
    thr = max(thr, 1e-4)
    return rms > thr


def _simple_peak_rate(rms: np.ndarray, sr: int, hop: int) -> Optional[float]:
    if rms.size < 8:
        return None

    w = 5
    smooth = np.convolve(rms, np.ones(w) / w, mode="same")

    min_sep = max(1, int(0.12 * sr / hop))

    p60 = float(np.percentile(smooth, 60))
    p90 = float(np.percentile(smooth, 90))
    thr = p60 + 0.30 * (p90 - p60)

    peaks = 0
    last_peak = -10**9
    for i in range(1, smooth.size - 1):
        if i - last_peak < min_sep:
            continue
        if smooth[i] > thr and smooth[i] >= smooth[i - 1] and smooth[i] >= smooth[i + 1]:
            peaks += 1
            last_peak = i

    duration = (smooth.size * hop) / float(sr)
    if duration <= 0:
        return None
    return float(peaks / duration)


def _breathiness_proxy(x: np.ndarray, sr: int) -> Optional[float]:
    if x.size < sr // 4:
        return None

    n = 2048
    if x.size < n:
        xx = np.pad(x, (0, n - x.size), mode="constant")
    else:
        xx = x[:n]

    win = np.hanning(xx.size).astype(np.float32)
    X = np.fft.rfft(xx * win)
    freqs = np.fft.rfftfreq(xx.size, d=1.0 / sr)
    mag2 = (np.abs(X) ** 2) + 1e-12

    total = float(np.sum(mag2))
    if total <= 0:
        return None

    hi = float(np.sum(mag2[freqs >= 3000]))
    return float(hi / total)


def _yin_pitch_frame(
    frame: np.ndarray,
    sr: int,
    fmin: float = 60.0,
    fmax: float = 400.0,
    thresh: float = 0.10,
) -> Optional[float]:
    frame = frame.astype(np.float64)
    frame = frame - np.mean(frame)

    if np.max(np.abs(frame)) < 1e-3:
        return None

    tau_min = int(sr / fmax)
    tau_max = int(sr / fmin)

    if tau_max <= tau_min + 2:
        return None
    if tau_max >= frame.size:
        tau_max = frame.size - 1
    if tau_max <= tau_min + 2:
        return None

    d = np.zeros(tau_max + 1, dtype=np.float64)
    for tau in range(1, tau_max + 1):
        diff = frame[:-tau] - frame[tau:]
        d[tau] = np.sum(diff * diff)

    cmnd = np.ones_like(d)
    running_sum = 0.0
    for tau in range(1, tau_max + 1):
        running_sum += d[tau]
        cmnd[tau] = d[tau] * tau / (running_sum + 1e-12)

    tau = None
    for t in range(tau_min, tau_max):
        if cmnd[t] < thresh and cmnd[t] <= cmnd[t + 1]:
            tau = t
            break

    if tau is None:
        tau = int(np.argmin(cmnd[tau_min:tau_max]) + tau_min)

    if tau <= 0:
        return None

    if 1 <= tau < tau_max:
        y0, y1, y2 = cmnd[tau - 1], cmnd[tau], cmnd[tau + 1]
        denom = (y0 - 2 * y1 + y2)
        if abs(denom) > 1e-12:
            tau = tau + 0.5 * (y0 - y2) / denom

    f0 = float(sr / tau) if tau > 0 else None
    if f0 is None:
        return None
    if f0 < fmin or f0 > fmax:
        return None
    return f0


def _estimate_pitch_yin(
    x: np.ndarray,
    sr: int,
    voiced_mask: np.ndarray,
    frame: int,
    hop: int,
) -> Tuple[Optional[float], Optional[float]]:
    if voiced_mask.size == 0:
        return None, None

    f0s = []
    for i, voiced in enumerate(voiced_mask):
        if not voiced:
            continue

        start = i * hop
        seg = x[start : start + frame]
        if seg.size < frame:
            seg = np.pad(seg, (0, frame - seg.size), mode="constant")

        f0 = _yin_pitch_frame(seg, sr=sr)
        if f0 is not None:
            f0s.append(f0)

    if len(f0s) < 10:
        return None, None

    arr = np.array(f0s, dtype=np.float64)
    pitch_median = float(np.median(arr))
    pitch_variability = float(np.std(arr))
    return pitch_variability, pitch_median


def analyze_wav_features(wav_path: Path) -> Dict[str, float | None]:
    _require_soundfile()

    wav_path = Path(wav_path)
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV not found: {wav_path}")

    x, sr = sf.read(str(wav_path), always_2d=False)
    if x is None or len(x) == 0:
        raise RuntimeError("Audio empty/unreadable")

    if hasattr(x, "ndim") and x.ndim > 1:
        x = np.mean(x, axis=1)

    x = np.asarray(x, dtype=np.float32)

    max_abs = float(np.max(np.abs(x)) + 1e-12)
    if max_abs > 1.5:
        x = x / max_abs

    duration = float(x.size / float(sr))

    frame = max(1, int(0.025 * sr))
    hop = max(1, int(0.010 * sr))
    rms = _frame_rms(x, frame=frame, hop=hop)

    rms_mean = float(np.mean(rms)) if rms.size else None
    rms_p95 = float(np.percentile(rms, 95)) if rms.size else None
    rms_std = float(np.std(rms)) if rms.size else None
    rms_cv = float(rms_std / (rms_mean + 1e-12)) if (rms_mean is not None and rms_std is not None) else None

    clip_fraction = float(np.mean(np.abs(x) >= 0.98)) if x.size else None

    voiced_mask = _robust_voiced_mask(rms)
    voiced_fraction = float(np.mean(voiced_mask)) if voiced_mask.size else None
    pause_fraction = float(np.mean(~voiced_mask)) if voiced_mask.size else None

    speech_rate_est = _simple_peak_rate(rms, sr=sr, hop=hop)
    breathiness_score = _breathiness_proxy(x, sr=sr)

    pitch_variability, pitch_median = _estimate_pitch_yin(
        x=x, sr=sr, voiced_mask=voiced_mask, frame=frame, hop=hop
    )

    return {
        "duration_seconds": duration,
        "pause_fraction": pause_fraction,
        "voiced_fraction": voiced_fraction,
        "speech_rate_est": speech_rate_est,
        "breathiness_score": breathiness_score,
        "pitch_variability": pitch_variability,
        "pitch_median": pitch_median,
        "rms_mean": rms_mean,
        "rms_p95": rms_p95,
        "rms_std": rms_std,
        "rms_cv": rms_cv,
        "clip_fraction": clip_fraction,
    }