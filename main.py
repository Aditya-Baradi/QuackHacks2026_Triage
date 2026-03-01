from __future__ import annotations

import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from typing import Any

from config import OUTPUTS_DIR, TMP_DIR
from models import LogQuestionRequest
from services.audio_analyzer import analyze_wav_features
from services.transcription import transcribe_wav
from utils.ffmpeg import convert_webm_to_wav

# --- Web server (dashboard) ---
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware


# -----------------------------
# Existing helpers (unchanged)
# -----------------------------
def _sanitize_segment(value: str | int) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value))


def _build_output_dir(patient_id: str, session_id: str) -> Path:
    patient_segment = _sanitize_segment(patient_id)
    session_segment = _sanitize_segment(session_id)
    return OUTPUTS_DIR / f"patient_{patient_segment}" / f"session_{session_segment}"


def _build_output_path(patient_id: str, session_id: str, question_id: str | int) -> Path:
    return _build_output_dir(patient_id, session_id) / f"q{_sanitize_segment(question_id)}_analysis.txt"


def _build_transcript_path(patient_id: str, session_id: str, question_id: str | int) -> Path:
    return _build_output_dir(patient_id, session_id) / f"q{_sanitize_segment(question_id)}_transcript.txt"


def _next_question_id(output_dir: Path) -> int:
    pattern = re.compile(r"q(\d+)_analysis\.txt")
    max_qid = 0
    if output_dir.exists():
        for path in output_dir.iterdir():
            if not path.is_file():
                continue
            match = pattern.fullmatch(path.name)
            if match is None:
                continue
            qid = int(match.group(1))
            max_qid = max(max_qid, qid)
    return max_qid + 1


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _format_metric(value: float | None, decimals: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f}"


def _quote_text(value: str | None) -> str:
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _contains_any(text_lower: str, phrases: list[str]) -> bool:
    return any(p in text_lower for p in phrases)


def _token_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def _is_wav(path: Path) -> bool:
    return path.suffix.lower() == ".wav"


def _is_webm(path: Path) -> bool:
    return path.suffix.lower() == ".webm"


# -----------------------------
# Your pipeline (unchanged)
# -----------------------------
def analyze_audio_file(
    input_audio: Path,
    patient_id: str | None = None,
    session_id: str | None = None,
    question_text: str = "",
    was_repeat: bool = False,
    repeat_reason: str = "",
) -> tuple[Path, Path]:
    """
    Main pipeline:
    - Save/convert to wav if needed
    - Transcribe
    - Extract features
    - Compute flags
    - Write transcript + analysis files
    Returns (analysis_path, transcript_path)
    """
    patient_id = patient_id or "auto_patient"
    session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d')}"

    output_dir = _build_output_dir(patient_id, session_id)
    question_id = str(_next_question_id(output_dir))

    output_path = _build_output_path(patient_id, session_id, question_id)
    transcript_path = _build_transcript_path(patient_id, session_id, question_id)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = uuid4().hex

    # Copy input into tmp (keeps things reproducible)
    src = Path(input_audio)
    if not src.exists():
        raise FileNotFoundError(f"Input audio not found: {src}")

    tmp_input = TMP_DIR / f"{upload_id}{src.suffix.lower()}"
    shutil.copyfile(src, tmp_input)

    # Ensure wav
    wav_path = TMP_DIR / f"{upload_id}.wav"
    if _is_wav(tmp_input):
        wav_path = tmp_input
    elif _is_webm(tmp_input):
        convert_webm_to_wav(tmp_input, wav_path)
    else:
        raise ValueError("Unsupported audio format. Use .wav or .webm")

    # -----------------------------
    # Transcription
    # -----------------------------
    transcript = ""
    transcription_failed = False
    try:
        transcript = transcribe_wav(wav_path).strip()
    except Exception:
        transcript = ""
        transcription_failed = True

    transcript_text = transcript.strip()
    tl = transcript_text.lower()

    # transcript-only file (2-file requirement)
    _write_text_file(transcript_path, f"{transcript_text}\n" if transcript_text else "\n")

    # -----------------------------
    # Feature extraction
    # -----------------------------
    feature_extraction_failed = False
    features: dict[str, float | None] = {
        "duration_seconds": None,
        "pause_fraction": None,
        "voiced_fraction": None,
        "speech_rate_est": None,
        "breathiness_score": None,
        "pitch_variability": None,
        "pitch_median": None,
        "rms_mean": None,
        "rms_p95": None,
        "rms_std": None,
        "rms_cv": None,
        "clip_fraction": None,
    }

    try:
        extracted = analyze_wav_features(wav_path)
        features.update(extracted)
    except Exception:
        feature_extraction_failed = True

    duration_seconds = features["duration_seconds"]
    pause_fraction = features["pause_fraction"]
    voiced_fraction = features["voiced_fraction"]
    speech_rate_est = features["speech_rate_est"]
    breathiness_score = features["breathiness_score"]
    pitch_variability = features["pitch_variability"]
    pitch_median = features["pitch_median"]
    rms_mean = features["rms_mean"]
    rms_p95 = features["rms_p95"]
    rms_std = features["rms_std"]
    rms_cv = features["rms_cv"]
    clip_fraction = features["clip_fraction"]

    # -----------------------------
    # Core flags
    # -----------------------------
    word_count = _token_count(transcript_text)
    speech_rate_low = speech_rate_est is not None and speech_rate_est < 1.2

    audio_pickup_issue = (
        transcript_text == ""
        or transcription_failed
        or (duration_seconds is not None and duration_seconds < 1.0)
        or (rms_mean is not None and rms_mean < 0.005)
        or (voiced_fraction is not None and voiced_fraction < 0.10)
    )

    response_unclear = (
        word_count < 3
        or "[inaudible]" in tl
        or (pause_fraction is not None and pause_fraction > 0.45 and speech_rate_low)
    )

    # -----------------------------
    # Text indicators (kept)
    # -----------------------------
    question_confusion = _contains_any(
        tl,
        [
            "i don't understand the question",
            "i dont understand the question",
            "i don't understand",
            "i dont understand",
            "what do you mean",
            "repeat the question",
            "can you repeat the question",
            "i'm not sure what you're asking",
            "im not sure what you're asking",
            "what are you asking",
        ],
    )

    text_disorientation_trigger = _contains_any(
        tl,
        [
            "i don't know where i am",
            "i dont know where i am",
            "where am i",
            "i'm disoriented",
            "im disoriented",
            "i don't know what day it is",
            "i dont know what day it is",
            "i don't know what time it is",
            "i dont know what time it is",
            "i don't know what's happening",
            "i dont know what's happening",
            "i can't remember what happened",
            "i cant remember what happened",
            "i don't remember what happened",
            "i dont remember what happened",
            "i woke up confused",
        ],
    )

    confusion_or_disorientation = text_disorientation_trigger

    # -----------------------------
    # possible_slurred_speech (AUDIO METRICS ONLY)
    # -----------------------------
    possible_slurred_speech = (
        (speech_rate_est is not None and speech_rate_est < 0.8)
        and (pause_fraction is not None and pause_fraction < 0.40)
        and (voiced_fraction is not None and voiced_fraction > 0.50)
        and (duration_seconds is not None and duration_seconds >= 2.0)
        and (pitch_variability is not None and pitch_variability < 35.0)
    )

    very_slow_speech = (
        speech_rate_est is not None
        and duration_seconds is not None
        and duration_seconds >= 4.0
        and speech_rate_est > 0
        and speech_rate_est < 0.75
    )

    long_pauses = (
        pause_fraction is not None
        and duration_seconds is not None
        and duration_seconds >= 4.0
        and pause_fraction >= 0.70
    )

    disorientation_possible = bool(
        text_disorientation_trigger
        or (question_confusion and (possible_slurred_speech or very_slow_speech or long_pauses))
    )

    # -----------------------------
    # Feeling / affect flags (AUDIO ONLY)
    # -----------------------------
    agitated_or_panicked_voice = (
        speech_rate_est is not None
        and pause_fraction is not None
        and breathiness_score is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and speech_rate_est > 4.0
        and pause_fraction < 0.35
        and breathiness_score > 0.20
    )

    calm_steady_voice = (
        speech_rate_est is not None
        and pause_fraction is not None
        and breathiness_score is not None
        and clip_fraction is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and 1.0 <= speech_rate_est <= 3.5
        and pause_fraction < 0.45
        and breathiness_score < 0.20
        and clip_fraction < 0.01
    )

    fatigued_or_low_energy_voice = (
        rms_p95 is not None
        and pause_fraction is not None
        and speech_rate_est is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and rms_p95 < 0.01
        and (pause_fraction > 0.55 or speech_rate_est < 1.0)
    )

    strained_or_breathing_effort_voice = (
        breathiness_score is not None
        and pause_fraction is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and breathiness_score > 0.30
        and pause_fraction > 0.50
    )

    weak_projection_or_whispery = (
        rms_p95 is not None
        and voiced_fraction is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and rms_p95 < 0.008
        and voiced_fraction > 0.30
    )

    overly_loud_or_shouting = (
        clip_fraction is not None
        and rms_p95 is not None
        and duration_seconds is not None
        and duration_seconds >= 1.5
        and (clip_fraction >= 0.02 or rms_p95 >= 0.06)
    )

    tremulous_or_unsteady_voice = (
        pitch_variability is not None
        and voiced_fraction is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and voiced_fraction > 0.50
        and pitch_variability > 80.0
    )

    monotone_or_flat_affect = (
        pitch_variability is not None
        and voiced_fraction is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and voiced_fraction > 0.50
        and pitch_variability < 25.0
    )

    hesitant_or_searching_for_words = (
        pause_fraction is not None
        and speech_rate_est is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and pause_fraction > 0.55
        and speech_rate_est < 1.2
    )

    disconnected_audio_or_background_noise = (
        rms_cv is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and rms_cv > 1.5
    )

    max_voice_bonus = (
        rms_p95 is not None
        and speech_rate_est is not None
        and duration_seconds is not None
        and duration_seconds >= 2.0
        and rms_p95 >= 0.04
        and speech_rate_est >= 3.8
    )

    # -----------------------------
    # Flags list
    # -----------------------------
    flags: list[str] = []

    if was_repeat:
        flags.append("repeat_requested")
    if audio_pickup_issue:
        flags.append("audio_pickup_issue")
    if response_unclear:
        flags.append("response_unclear")
    if possible_slurred_speech:
        flags.append("possible_slurred_speech")
    if feature_extraction_failed:
        flags.append("feature_extraction_failed")
    if question_confusion:
        flags.append("question_confusion")
    if disorientation_possible:
        flags.append("disorientation_possible")
    if confusion_or_disorientation:
        flags.append("confusion_or_disorientation")

    affect_candidates = {
        "overly_loud_or_shouting": overly_loud_or_shouting,
        "agitated_or_panicked_voice": agitated_or_panicked_voice,
        "strained_or_breathing_effort_voice": strained_or_breathing_effort_voice,
        "fatigued_or_low_energy_voice": fatigued_or_low_energy_voice,
        "weak_projection_or_whispery": weak_projection_or_whispery,
        "hesitant_or_searching_for_words": hesitant_or_searching_for_words,
        "calm_steady_voice": calm_steady_voice,
        "max_voice_bonus": max_voice_bonus,
        "disconnected_audio_or_background_noise": disconnected_audio_or_background_noise,
        "tremulous_or_unsteady_voice": tremulous_or_unsteady_voice,
        "monotone_or_flat_affect": monotone_or_flat_affect,
    }

    affect_priority = [
        "overly_loud_or_shouting",
        "agitated_or_panicked_voice",
        "strained_or_breathing_effort_voice",
        "fatigued_or_low_energy_voice",
        "weak_projection_or_whispery",
        "hesitant_or_searching_for_words",
        "calm_steady_voice",
        "max_voice_bonus",
        "disconnected_audio_or_background_noise",
        "tremulous_or_unsteady_voice",
        "monotone_or_flat_affect",
    ]

    primary_affect = None
    for name in affect_priority:
        if affect_candidates.get(name):
            primary_affect = name
            break

    if primary_affect:
        flags.append(primary_affect)

    conflict_groups = [
        {"calm_steady_voice", "agitated_or_panicked_voice"},
        {"fatigued_or_low_energy_voice", "max_voice_bonus"},
        {"weak_projection_or_whispery", "overly_loud_or_shouting"},
        {"monotone_or_flat_affect", "tremulous_or_unsteady_voice"},
    ]

    def conflicts(a: str | None, b: str) -> bool:
        if a is None:
            return False
        for grp in conflict_groups:
            if a in grp and b in grp:
                return True
        return False

    secondary_allowlist = [
        "disconnected_audio_or_background_noise",
        "tremulous_or_unsteady_voice",
        "monotone_or_flat_affect",
        "hesitant_or_searching_for_words",
    ]

    for name in secondary_allowlist:
        if not affect_candidates.get(name):
            continue
        if name == primary_affect:
            continue
        if conflicts(primary_affect, name):
            continue
        flags.append(name)

    # De-duplicate preserving order
    seen = set()
    flags = [x for x in flags if not (x in seen or seen.add(x))]

    # -----------------------------
    # Output formatting (same format)
    # -----------------------------
    audio_quality = "poor" if (audio_pickup_issue or feature_extraction_failed) else "ok"
    repeat_value = "YES" if was_repeat else "NO"
    pickup_value = "YES" if audio_pickup_issue else "NO"
    clarity_value = "unclear" if response_unclear else "clear"
    flags_block = "\n".join(f"- {flag}" for flag in flags) if flags else "<none>"

    findings_text = (
        f"PATIENT: {patient_id}\n"
        f"SESSION: {session_id}\n"
        f"QUESTION: {question_id}\n"
        f"QUESTION_TEXT: \"{_quote_text(question_text)}\"\n"
        "ANSWER_MODE: UPLOADED\n"
        f"REPEAT: {repeat_value}\n"
        f"REPEAT_REASON: \"{_quote_text(repeat_reason)}\"\n"
        "\n"
        "TRANSCRIPT:\n"
        f"\"{_quote_text(transcript_text)}\"\n"
        "\n"
        "INTERACTION QUALITY\n"
        f"- audio_quality: {audio_quality}\n"
        f"- audio_pickup_issue: {pickup_value}\n"
        f"- response_clarity: {clarity_value}\n"
        f"- repeat_requested: {repeat_value}\n"
        "\n"
        "AUDIO FINDINGS\n"
        f"Duration: {_format_metric(duration_seconds, 2)}\n"
        f"Pause fraction: {_format_metric(pause_fraction, 3)}\n"
        f"Voiced fraction: {_format_metric(voiced_fraction, 3)}\n"
        f"Speech rate estimate: {_format_metric(speech_rate_est, 3)}\n"
        f"Breathiness score: {_format_metric(breathiness_score, 3)}\n"
        f"Pitch variability: {_format_metric(pitch_variability, 3)}\n"
        f"Pitch median: {_format_metric(pitch_median, 3)}\n"
        f"RMS mean: {_format_metric(rms_mean, 6)}\n"
        f"RMS p95: {_format_metric(rms_p95, 6)}\n"
        f"RMS std: {_format_metric(rms_std, 6)}\n"
        f"Clip fraction: {_format_metric(clip_fraction, 4)}\n"
        f"RMS CV: {_format_metric(rms_cv, 3)}\n"
        "\n"
        "FLAGS:\n"
        f"{flags_block}\n"
    )

    _write_text_file(output_path, findings_text)
    return output_path, transcript_path


def log_question(payload: LogQuestionRequest) -> tuple[Path, Path]:
    output_path = _build_output_path(payload.patient_id, payload.session_id, payload.question_id)
    transcript_path = _build_transcript_path(payload.patient_id, payload.session_id, payload.question_id)

    answer_mode_upper = "SKIPPED" if payload.answer_mode == "skipped" else "DONT_KNOW"
    repeat_value = "YES" if payload.was_repeat else "NO"
    transcript_line = "<skipped>" if payload.answer_mode == "skipped" else "\"I don't know.\""

    transcript_only = "" if payload.answer_mode == "skipped" else "I don't know."
    _write_text_file(transcript_path, f"{transcript_only}\n" if transcript_only else "\n")

    mode_flag = "skipped_question" if payload.answer_mode == "skipped" else "dont_know"

    flags = []
    if payload.was_repeat:
        flags.append("- repeat_requested")
    flags.append(f"- {mode_flag}")
    flags_block = "\n".join(flags)

    summary_text = (
        f"Question result is {'skipped' if payload.answer_mode == 'skipped' else 'dont_know'}."
        if not payload.was_repeat
        else f"Question result is {'skipped' if payload.answer_mode == 'skipped' else 'dont_know'}. Repeat was requested."
    )

    findings_text = (
        f"PATIENT: {payload.patient_id}\n"
        f"SESSION: {payload.session_id}\n"
        f"QUESTION: {payload.question_id}\n"
        f"QUESTION_TEXT: \"{payload.question_text}\"\n"
        f"ANSWER_MODE: {answer_mode_upper}\n"
        f"SKIP_REASON: \"{payload.skip_reason or ''}\"\n"
        f"REPEAT: {repeat_value}\n"
        f"REPEAT_REASON: \"{payload.repeat_reason or ''}\"\n"
        "\n"
        "TRANSCRIPT:\n"
        f"{transcript_line}\n"
        "\n"
        "INTERACTION QUALITY\n"
        "- audio_quality: n/a\n"
        "- audio_pickup_issue: n/a\n"
        "- response_clarity: n/a\n"
        f"- repeat_requested: {repeat_value}\n"
        "\n"
        "AUDIO FINDINGS\n"
        "<n/a>\n"
        "\n"
        "FLAGS:\n"
        f"{flags_block}\n"
        "\n"
        "SUMMARY:\n"
        f"{summary_text}\n"
    )

    _write_text_file(output_path, findings_text)
    return output_path, transcript_path


# ==========================================================
# PATIENT WEBSITE + QUESTIONS (NEW)
# ==========================================================
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# You can loosen/tighten this later. This lets localhost frontends work.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_questions() -> list[dict[str, Any]]:
    """
    Tries to load questions from Questions.py.
    Supports common patterns:
      - module dicts named section_*, symptoms_*, voice_analysis_prompts
    Output: [{"id": 1, "text": "..."}...]
    """
    questions: list[dict[str, Any]] = []
    try:
        import Questions as Q  # Questions.py in your root
    except Exception:
        # fallback if Questions.py isn't available
        return [
            {"id": 1, "text": "What brings you in today?"},
            {"id": 2, "text": "When did your symptoms start?"},
            {"id": 3, "text": "On a scale of 1 to 10, how severe is it?"},
        ]

    def add_from_dict(d: dict[Any, Any]) -> None:
        for k in sorted(d.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
            try:
                qid = int(k)
            except Exception:
                continue
            text = str(d.get(k, "")).strip()
            if not text:
                continue
            questions.append({"id": qid, "text": text})

    # Prefer explicit ordering if you have it
    preferred_names = [
        "section_1_danger_screening",
        "section_2_chief_complaint",
        "section_4_risk_factors",
        "section_5_meds_allergies",
        "section_6_mental_health",
        "section_7_logistics",
        "voice_analysis_prompts",
    ]

    # Add preferred sections first
    for name in preferred_names:
        obj = getattr(Q, name, None)
        if isinstance(obj, dict):
            add_from_dict(obj)

    # Then any other question dicts
    for name in dir(Q):
        if name in preferred_names:
            continue
        if name.startswith("section_") or name.startswith("symptoms_"):
            obj = getattr(Q, name, None)
            if isinstance(obj, dict):
                add_from_dict(obj)

    # De-duplicate by id preserving order
    seen: set[int] = set()
    deduped: list[dict[str, Any]] = []
    for item in questions:
        qid = int(item["id"])
        if qid in seen:
            continue
        seen.add(qid)
        deduped.append(item)

    return deduped if deduped else [
        {"id": 1, "text": "What brings you in today?"},
        {"id": 2, "text": "When did your symptoms start?"},
    ]


@app.get("/api/questions")
def api_questions():
    return {"questions": _load_questions()}

from typing import Any

def _flow_questions(pathway: int) -> list[dict[str, Any]]:
    import Questions as q

    symptom_map = {
        1: q.symptoms_chest_heart,
        2: q.symptoms_breathing,
        3: q.symptoms_stroke_neuro,
        4: q.symptoms_abdominal,
        5: q.symptoms_fever_infection,
        6: q.symptoms_injury_trauma,
    }
    symptom_dict = symptom_map.get(pathway, q.symptoms_chest_heart)

    def add_group(d: dict[int, str], group: str) -> list[dict[str, Any]]:
        return [{"id": k, "text": v, "group": group} for k, v in sorted(d.items(), key=lambda x: x[0])]

    # EXACT order you listed
    out: list[dict[str, Any]] = []
    out += add_group(q.section_7_logistics, "logistics")
    out += add_group(q.section_1_danger_screening, "danger")
    out += add_group(q.section_2_chief_complaint, "chief")
    out += add_group(symptom_dict, "symptoms")
    out += add_group(q.section_4_risk_factors, "risk")
    out += add_group(q.section_5_meds_allergies, "meds")
    out += add_group(q.section_6_mental_health, "mental")
    out += add_group(q.voice_analysis_prompts, "voice")
    return out


@app.get("/api/flow")
def api_flow(pathway: int = 1):
    if pathway not in (1, 2, 3, 4, 5, 6):
        pathway = 1
    try:
        return {"pathway": pathway, "questions": _flow_questions(pathway)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load Questions.py: {e}")

@app.get("/patient", response_class=HTMLResponse)
def patient_page():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Patient Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 820px; margin: 40px auto; padding: 0 16px; }
    .card { border: 1px solid #ddd; border-radius: 14px; padding: 18px; }
    #qText { font-size: 22px; line-height: 1.25; margin: 10px 0 14px; cursor: pointer; }
    .muted { color: #555; font-size: 14px; }
    .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    #recordBtn { font-size: 18px; padding: 14px 18px; border-radius: 12px; border: none; cursor: pointer; min-width: 240px; }
    .idle { background: #111; color: #fff; }
    .rec  { background: #b00020; color: #fff; }
    label { font-size: 13px; color: #333; display: block; margin-top: 10px; margin-bottom: 6px; }
    input, select { width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; }
    pre { white-space: pre-wrap; background: #f7f7f7; padding: 12px; border-radius: 10px; }
    .tiny { font-size: 12px; color: #666; }
  </style>
</head>
<body>
  <h1>Patient Dashboard</h1>

  <div class="card">
    <div class="muted">
      Question is spoken out loud. Click question text to replay.
    </div>

    <label>Pathway</label>
    <select id="pathway">
      <option value="1">1 — Chest / Heart</option>
      <option value="2">2 — Breathing</option>
      <option value="3">3 — Stroke / Neuro</option>
      <option value="4">4 — Abdominal</option>
      <option value="5">5 — Fever / Infection</option>
      <option value="6">6 — Injury / Trauma</option>
    </select>

    <div id="qText">Loading...</div>
    <div class="tiny" id="qMeta"></div>

    <div class="row" style="margin-top: 12px;">
      <button id="recordBtn" class="idle">Start Recording</button>
      <span id="status" class="muted">Idle</span>
    </div>

    <label>Patient ID</label>
    <input id="patientId" value="auto_patient" />

    <label>Session ID (optional)</label>
    <input id="sessionId" placeholder="leave blank to auto-generate" />

    <label>Last upload result</label>
    <pre id="resultBox">Waiting…</pre>
  </div>

<script>
/**
 * ✅ CHANGE ORDER HERE
 * This array controls the chatbot order on the frontend.
 * Valid group names: logistics, danger, chief, symptoms, risk, meds, mental, voice
 */
const ORDER = ["logistics", "danger", "chief", "symptoms", "risk", "meds", "mental", "voice"];
// Example alternative:
// const ORDER = ["danger", "chief", "symptoms", "risk", "meds", "mental", "logistics", "voice"];

let groups = {};         // { groupName: [q,q,q] }
let flatQuestions = [];  // final flattened list in ORDER
let idx = 0;

let mediaRecorder = null;
let chunks = [];
let isRecording = false;

const qTextEl = document.getElementById("qText");
const qMetaEl = document.getElementById("qMeta");
const recordBtn = document.getElementById("recordBtn");
const statusEl = document.getElementById("status");
const resultBox = document.getElementById("resultBox");
const pathwayEl = document.getElementById("pathway");

function speak(text) {
  try {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.0; u.pitch = 1.0; u.volume = 1.0;
    window.speechSynthesis.speak(u);
  } catch (e) {}
}

function buildGroups(questionList) {
  const g = {};
  for (const q of questionList) {
    const name = q.group || "unknown";
    if (!g[name]) g[name] = [];
    g[name].push(q);
  }
  // Keep natural order within each group based on the backend list order.
  return g;
}

function flattenByOrder(g) {
  const out = [];
  for (const groupName of ORDER) {
    if (g[groupName] && g[groupName].length) {
      out.push(...g[groupName]);
    }
  }
  return out;
}

function renderQuestion() {
  if (!flatQuestions.length) {
    qTextEl.textContent = "No questions available.";
    qMetaEl.textContent = "";
    return;
  }
  if (idx >= flatQuestions.length) {
    qTextEl.textContent = "All questions completed. Thank you.";
    qMetaEl.textContent = "";
    speak("All questions completed. Thank you.");
    return;
  }
  const q = flatQuestions[idx];
  qTextEl.textContent = q.text;
  qMetaEl.textContent = `#${idx + 1}/${flatQuestions.length}   (Group: ${q.group}, ID: ${q.id})`;
  speak(q.text);
}

qTextEl.addEventListener("click", () => {
  if (flatQuestions.length && idx < flatQuestions.length) speak(flatQuestions[idx].text);
});

function setUIRecording(on) {
  isRecording = on;
  if (on) {
    recordBtn.textContent = "Stop Recording";
    recordBtn.classList.remove("idle");
    recordBtn.classList.add("rec");
    statusEl.textContent = "Recording…";
  } else {
    recordBtn.textContent = "Start Recording";
    recordBtn.classList.remove("rec");
    recordBtn.classList.add("idle");
    statusEl.textContent = "Idle";
  }
}

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  chunks = [];
  mediaRecorder = new MediaRecorder(stream);

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) chunks.push(e.data);
  };

  mediaRecorder.onstop = async () => {
    try {
      const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
      await uploadRecording(blob);
    } catch (err) {
      resultBox.textContent = "Upload failed: " + err;
    }
  };

  mediaRecorder.start();
  setUIRecording(true);
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  setUIRecording(false);
}

async function uploadRecording(blob) {
  resultBox.textContent = "Uploading + analyzing…";

  const patientId = document.getElementById("patientId").value || "auto_patient";
  const sessionId = document.getElementById("sessionId").value || "";

  const q = flatQuestions[idx] || { text: "" };

  const fd = new FormData();
  fd.append("file", blob, "response.webm");
  fd.append("patient_id", patientId);
  fd.append("session_id", sessionId);
  fd.append("question_text", q.text);

  const res = await fetch("/api/analyze", { method: "POST", body: fd });
  const data = await res.json();

  if (!res.ok) {
    resultBox.textContent = "Error: " + (data.detail || JSON.stringify(data));
    return;
  }

  resultBox.textContent = JSON.stringify(data, null, 2);

  // advance
  idx += 1;
  renderQuestion();
}

recordBtn.addEventListener("click", async () => {
  try {
    if (!isRecording) await startRecording();
    else stopRecording();
  } catch (err) {
    resultBox.textContent = "Mic error: " + err;
  }
});

async function loadFlow() {
  const pathway = pathwayEl.value || "1";
  const res = await fetch(`/api/flow?pathway=${encodeURIComponent(pathway)}`);
  const data = await res.json();

  const list = data.questions || [];
  groups = buildGroups(list);
  flatQuestions = flattenByOrder(groups);

  idx = 0;
  renderQuestion();
}

pathwayEl.addEventListener("change", loadFlow);

loadFlow();
</script>
</body>
</html>
    """


@app.post("/api/analyze")
async def api_analyze(
    file: UploadFile = File(...),
    patient_id: str = Form("auto_patient"),
    session_id: str = Form(""),
    question_text: str = Form(""),
):
    """
    Receives browser-recorded webm audio, saves to TMP, runs your existing analyze_audio_file.
    """
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Save upload to a temp file
    suffix = ".webm"
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1].lower()

    upload_id = uuid4().hex
    tmp_input = TMP_DIR / f"{upload_id}{suffix}"

    try:
        raw = await file.read()
        tmp_input.write_bytes(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {e}")

    # Run pipeline (supports wav or webm)
    try:
        analysis_path, transcript_path = analyze_audio_file(
            input_audio=tmp_input,
            patient_id=patient_id or "auto_patient",
            session_id=session_id or None,
            question_text=question_text or "",
            was_repeat=False,
            repeat_reason="",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Best-effort cleanup of uploaded tmp file
        try:
            if tmp_input.exists():
                tmp_input.unlink()
        except Exception:
            pass

    # Return a small preview
    transcript_preview = ""
    try:
        transcript_preview = transcript_path.read_text(encoding="utf-8")[:2000]
    except Exception:
        transcript_preview = ""

    return JSONResponse(
        {
            "ok": True,
            "analysis_path": str(analysis_path),
            "transcript_path": str(transcript_path),
            "transcript_preview": transcript_preview,
            "patient_id": patient_id or "auto_patient",
            "session_id": session_id or None,
            "question_text": question_text or "",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


# -----------------------------
# Keep your old local test main()
# -----------------------------
def main():
    print("HEY")
    audio_path = Path("C:\\TryingAgain\\Recording_3.wav")  # <-- put your file here

    analysis_path, transcript_path = analyze_audio_file(
        input_audio=audio_path,
        patient_id="auto_patient",
        session_id=None,  # auto-generates
        question_text="What is your name?",
        was_repeat=False,
        repeat_reason="",
    )

    print("Analysis written to:", analysis_path)
    print("Transcript written to:", transcript_path)


if __name__ == "__main__":
    # Running this file directly keeps your old behavior.
    # For the patient website, run:
    #   uvicorn main:app --reload --port 8000
    main()