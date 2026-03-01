🩺 QuackHacks 2026 — AI Voice Triage System

An AI-powered voice triage assistant that analyzes what a patient says and how they say it to generate structured, risk-aware triage reports in real time.

🚨 The Problem

Emergency and urgent care intake is:

Time-consuming

Subjective

Dependent on staff availability

Often inconsistent

Early triage decisions rely heavily on human interpretation of speech patterns, urgency, stress, and clarity.

We asked:

Can we build an AI system that performs a first-pass triage from voice alone?

💡 Our Solution

We built a system that:

Records patient voice responses

Transcribes them using Whisper

Extracts acoustic biomarkers from the signal

Flags risk patterns

Generates structured triage reports

It evaluates:

Content (NLP)

Speech rate

Pauses

Pitch variability

Energy patterns

Breathiness

Clipping / shouting indicators

This allows the system to detect both semantic red flags and vocal stress signals.

🏗️ System Architecture
Patient Voice
      ↓
Speech-to-Text (Faster-Whisper)
      ↓
Signal Processing (Librosa + NumPy)
      ↓
Heuristic Risk Flag Engine
      ↓
Structured Clinical-Style Report
      ↓
Optional MongoDB Storage

For the interactive mode:

LLM (OpenAI)
      ↓
Generates Next Triage Question
      ↓
ElevenLabs TTS (speaks question)
      ↓
Records Patient Response
      ↓
Audio Analysis Pipeline
🔬 What Makes This Innovative?

Unlike basic chatbot triage systems, this project:

Uses acoustic biomarkers, not just text

Detects shouting, clipped audio, breathiness

Estimates speech rate and pause fraction

Combines LLM-driven question flow with signal analysis

Produces structured machine-readable output

It merges:

NLP

Signal processing

LLM orchestration

Voice synthesis

Backend storage

All in a lightweight, hackathon-ready system.

📂 Key Components

main.py — Core analysis engine (analyze_audio_file)

Gemini.py — Interactive AI triage loop (LLM + TTS + recording)

services/transcription.py — Whisper-based transcription

services/audio_analyzer.py — Acoustic feature extraction

triageService.py — MongoDB patient management

Questions.py — Emergency + symptom question bank

⚡ Quick Start (Under 2 Minutes)
1️⃣ Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

Install ffmpeg if using .webm input.

Create a .env file:

OPENAI_API_KEY=...
ELEVEN_LABS_API_KEY=...
MONGODB_URI=...
MONGODB_DB_NAME=triage_db
2️⃣ Run Interactive Triage Assistant
python Gemini.py

The system will:

Ask a triage question

Speak it aloud

Record your answer

Analyze voice + content

Generate structured output

📊 Example Output

The system generates:

PATIENT: auto_patient
SESSION: session_20260228
QUESTION: 10

TRANSCRIPT:
"I feel pressure in my chest and I'm short of breath..."

AUDIO FINDINGS
Duration: 8.42
Speech rate estimate: 2.31
Pause fraction: 0.41
Pitch variability: 512.83
RMS mean: 0.0138

FLAGS:
- possible_distress
- elevated_vocal_intensity

Outputs are written to:

outputs/
  patient_<id>/
    session_<id>/
      q*_analysis.txt
      q*_transcript.txt
🎯 Potential Impact

This system could be extended to:

Remote telehealth pre-screening

AI nurse assistants

ER intake optimization

Mental health screening

Stress detection systems

Elderly monitoring platforms

It demonstrates how AI can augment early medical decision-making without replacing clinicians.

🧠 Tech Stack

Python

Faster-Whisper

Librosa

NumPy

OpenAI API

ElevenLabs TTS

MongoDB Atlas

🚧 Future Improvements

ML-based risk scoring instead of heuristics

Emotion classification model

Real-time streaming audio

Web dashboard

Clinical dataset validation

👤 Built For

QuackHacks 2026
AI + Healthcare Innovation Track
