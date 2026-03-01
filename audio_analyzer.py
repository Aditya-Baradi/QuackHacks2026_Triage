from pathlib import Path

import librosa
import numpy as np


def analyze_wav_features(path: str | Path) -> dict[str, float]:
    wav_path = Path(path)
    samples, sample_rate = librosa.load(str(wav_path), sr=16000, mono=True)

    if samples.size == 0:
        raise RuntimeError("Audio file contains no samples")

    duration_seconds = float(librosa.get_duration(y=samples, sr=sample_rate))

    frame_length = 1024
    hop_length = 256

    # RMS energy per frame (proxy for loudness over time)
    rms = librosa.feature.rms(y=samples, frame_length=frame_length, hop_length=hop_length)[0]
    rms_mean = float(np.mean(rms)) if rms.size else 0.0
    rms_std = float(np.std(rms)) if rms.size else 0.0
    rms_p95 = float(np.percentile(rms, 95)) if rms.size else 0.0

    # Coefficient of variation: how "jumpy" the loudness is (useful for noise/disconnect issues)
    rms_cv = float(rms_std / (rms_mean + 1e-8)) if rms.size else 0.0

    # Silence threshold based on lower-energy frames
    silence_floor = float(np.percentile(rms, 20)) if rms.size else 0.0
    silence_threshold = max(1e-4, silence_floor * 0.8)
    pause_fraction = float(np.mean(rms < silence_threshold)) if rms.size else 1.0

    # Voiced estimate fallback based on energy
    energy_voiced_threshold = max(1.5e-4, silence_threshold * 1.5)
    voiced_energy_mask = rms > energy_voiced_threshold if rms.size else np.array([], dtype=bool)

    # Pitch + voiced frames from pyin (best-effort)
    pitch_variability = 0.0
    pitch_median = 0.0
    voiced_fraction = 0.0

    try:
        f0, voiced_flag, _ = librosa.pyin(
            samples,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sample_rate,
            hop_length=hop_length,
        )

        if voiced_flag is not None and len(voiced_flag) > 0:
            voiced_fraction = float(np.mean(voiced_flag))
        else:
            voiced_fraction = float(np.mean(voiced_energy_mask)) if voiced_energy_mask.size else 0.0

        valid_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
        pitch_variability = float(np.std(valid_f0)) if valid_f0.size else 0.0
        pitch_median = float(np.median(valid_f0)) if valid_f0.size else 0.0
    except Exception:
        voiced_fraction = float(np.mean(voiced_energy_mask)) if voiced_energy_mask.size else 0.0
        pitch_variability = 0.0
        pitch_median = 0.0

    # Speech rate estimate via onset count (rough, but consistent)
    onset_frames = librosa.onset.onset_detect(
        y=samples,
        sr=sample_rate,
        hop_length=hop_length,
        units="frames",
        backtrack=False,
    )
    speech_rate_est = float(len(onset_frames) / max(duration_seconds, 1e-6))

    # Breathiness proxy: ratio of high-frequency energy to low-frequency energy
    spectrum = np.abs(librosa.stft(samples, n_fft=1024, hop_length=hop_length)) ** 2
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=1024)

    low_mask = (freqs >= 200) & (freqs <= 2000)
    high_mask = (freqs >= 4000) & (freqs <= 7900)

    low_energy = float(np.mean(spectrum[low_mask])) if np.any(low_mask) else 1e-8
    high_energy = float(np.mean(spectrum[high_mask])) if np.any(high_mask) else 0.0
    breathiness_score = float(high_energy / (low_energy + 1e-8))

    # Clipping proxy: fraction of samples near max amplitude (works reasonably on normalized audio)
    clip_fraction = float(np.mean(np.abs(samples) >= 0.98))

    return {
        "duration_seconds": duration_seconds,
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