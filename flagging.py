from __future__ import annotations

import re
from typing import Any


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().lower())


def derive_audio_flags(m: dict[str, float]) -> tuple[list[str], dict[str, str]]:
    """
    Sensitive-but-not-crazy thresholds. Tune later with real samples.
    Returns (flags, details).
    """
    flags: list[str] = []
    details: dict[str, str] = {}

    dur = float(m.get("duration_seconds", 0.0))
    pause = float(m.get("pause_fraction", 1.0))
    voiced = float(m.get("voiced_fraction", 0.0))
    rate = float(m.get("speech_rate_est", 0.0))
    breath = float(m.get("breathiness_score", 0.0))
    pitch_sd = float(m.get("pitch_variability", 0.0))
    rms_mean = float(m.get("rms_mean", 0.0))
    rms_p95 = float(m.get("rms_p95", 0.0))
    clip = float(m.get("clip_fraction", 0.0))

    def add(code: str, reason: str):
        if code not in flags:
            flags.append(code)
            details[code] = reason

    # Capture quality
    if clip >= 0.01:
        add("audio_clipping", f"clip_fraction={clip:.3f} (>=0.010 suggests distortion)")
    if (rms_p95 > 0 and rms_p95 < 0.01) or (rms_mean > 0 and rms_mean < 0.002):
        add("audio_very_quiet", f"rms_p95={rms_p95:.4f}, rms_mean={rms_mean:.4f} (very low volume)")
    if voiced < 0.20 and dur >= 2.0:
        add("audio_low_voicing", f"voiced_fraction={voiced:.3f} (<0.20)")

    # Pauses / hesitancy
    if pause >= 0.70 and dur >= 4.0:
        add("long_pauses", f"pause_fraction={pause:.3f} (>=0.70)")
    if pause >= 0.85 and dur >= 4.0:
        add("very_long_pauses", f"pause_fraction={pause:.3f} (>=0.85)")

    # Rate (crude estimate, keep thresholds generous)
    if 0 < rate < 0.75 and dur >= 4.0:
        add("very_slow_speech", f"speech_rate_est={rate:.3f} (<0.75)")
    if rate > 4.5 and dur >= 4.0:
        add("very_fast_speech", f"speech_rate_est={rate:.3f} (>4.5)")

    # Breathiness
    if breath >= 0.20 and dur >= 2.0:
        add("breathy_voice", f"breathiness_score={breath:.3f} (>=0.20)")
    if breath >= 0.35 and dur >= 2.0:
        add("very_breathy_voice", f"breathiness_score={breath:.3f} (>=0.35)")

    # Pitch instability (signal only)
    if pitch_sd >= 80.0 and dur >= 2.0:
        add("high_pitch_variability", f"pitch_variability={pitch_sd:.1f}Hz (>=80Hz)")
    if pitch_sd >= 140.0 and dur >= 2.0:
        add("very_high_pitch_variability", f"pitch_variability={pitch_sd:.1f}Hz (>=140Hz)")

    return flags, details


def derive_text_flags(transcript: str) -> tuple[list[str], dict[str, str]]:
    """
    Text triggers for triage signals.
    """
    t = _norm(transcript)
    flags: list[str] = []
    details: dict[str, str] = {}

    def add(code: str, reason: str):
        if code not in flags:
            flags.append(code)
            details[code] = reason

    # Confusion/disorientation
    confusion = [
        r"\bi don't know where i am\b",
        r"\bwhere am i\b",
        r"\bi('?m)? confused\b",
        r"\bi('?m)? disoriented\b",
        r"\bi don't remember\b",
        r"\bi can't remember\b",
    ]
    if any(re.search(p, t) for p in confusion):
        add("confusion_or_disorientation", "Mentions confusion/disorientation/unknown location")

    # Pain (routing + severity)
    if re.search(r"\b(back hurts|back pain|my back hurts)\b", t):
        add("back_pain_reported", "Mentions back pain")

    severe_pain = [
        r"\bworst pain\b",
        r"\b10/10\b",
        r"\bunbearable\b",
        r"\bsevere pain\b",
        r"\bextreme pain\b",
    ]
    if any(re.search(p, t) for p in severe_pain):
        add("severe_pain", "Mentions severe/unbearable pain")

    # Breathing
    breathing = [
        r"\b(can't breathe|cannot breathe)\b",
        r"\bshortness of breath\b",
        r"\btrouble breathing\b",
        r"\bchoking\b",
        r"\bgasping\b",
    ]
    if any(re.search(p, t) for p in breathing):
        add("breathing_difficulty", "Mentions difficulty breathing/choking")

    # Chest pain
    chest = [
        r"\bchest pain\b",
        r"\bpressure in (my )?chest\b",
        r"\btightness in (my )?chest\b",
    ]
    if any(re.search(p, t) for p in chest):
        add("chest_pain", "Mentions chest pain/pressure")

    # Neuro emergency
    neuro = [
        r"\bslurred speech\b",
        r"\bcan't speak\b",
        r"\b(face (is )?drooping|drooping face)\b",
        r"\bone side (is )?weak\b",
        r"\bnumb(ness)?\b",
        r"\bsudden headache\b",
    ]
    if any(re.search(p, t) for p in neuro):
        add("possible_neuro_emergency", "Mentions stroke-like symptoms")

    # Fainting/dizziness
    faint = [
        r"\bpassed out\b",
        r"\bfainted\b",
        r"\bblacked out\b",
        r"\bdizzy\b",
        r"\blightheaded\b",
    ]
    if any(re.search(p, t) for p in faint):
        add("syncope_or_dizziness", "Mentions fainting/dizziness")

    # Bleeding/injury
    injury = [
        r"\bbleeding\b",
        r"\bwon't stop bleeding\b",
        r"\bcut\b",
        r"\bstabbed\b",
        r"\bshot\b",
    ]
    if any(re.search(p, t) for p in injury):
        add("bleeding_or_injury", "Mentions bleeding/injury")

    return flags, details


def derive_all_flags(audio_metrics: dict[str, float], transcript: str) -> tuple[list[str], dict[str, str]]:
    a_flags, a_details = derive_audio_flags(audio_metrics)
    t_flags, t_details = derive_text_flags(transcript)

    flags = sorted(set(a_flags + t_flags))
    details = {**a_details, **t_details}
    return flags, details