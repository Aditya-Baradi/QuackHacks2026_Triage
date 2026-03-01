from typing import Literal

from pydantic import BaseModel


class LogQuestionRequest(BaseModel):
    patient_id: str
    session_id: str
    question_id: str
    question_text: str
    answer_mode: Literal["skipped", "dont_know"]
    skip_reason: str | None = None
    was_repeat: bool
    repeat_reason: str | None = None
