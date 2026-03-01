from dataclasses import dataclass
from typing import Optional


@dataclass
class LogQuestionRequest:
    patient_id: str
    session_id: str
    question_id: str
    question_text: str
    answer_mode: str  # "skipped" or "dont_know"
    was_repeat: bool = False
    repeat_reason: Optional[str] = None
    skip_reason: Optional[str] = None