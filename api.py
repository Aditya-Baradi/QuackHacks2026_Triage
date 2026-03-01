# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# These are from your existing code
from triageService import (
    create_patient,
    add_key_note,
    set_patient_priority,
    get_patient_details,
    sort_patients_by_priority,
    pop_admitted_patients_from_queue,
)
# db.py handles Mongo client + collections and .env loading :contentReference[oaicite:1]{index=1}

app = FastAPI(title="Quack & Assess API")

# ---------------- CORS (so your HTML/JS can talk to it) ----------------
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5500",  # VSCode Live Server
    "http://localhost:3000",  # if you use a dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Request body models ----------------

class PatientCreate(BaseModel):
    firstName: str
    lastName: str
    DOB: str
    phoneNumber: str
    gender: Optional[str] = None


class KeyNoteCreate(BaseModel):
    noteText: str
    createdBy: Optional[str] = None


class PriorityUpdate(BaseModel):
    priorityLevel: int
    priorityStatus: str = "waiting"
    reason: Optional[str] = None
    assignedNurse: Optional[str] = None


# ---------------- Routes ----------------

@app.get("/api/queue")
def api_queue():
    """
    Returns:
    [
      {
        "patient": {...},
        "keyNotes": [...],
        "triagePriority": {...},
        "numericPriority": int
      },
      ...
    ]
    """
    return sort_patients_by_priority()


@app.get("/api/patients/{patient_id}")
def api_get_patient(patient_id: str):
    details = get_patient_details(patient_id)
    if not details:
        raise HTTPException(status_code=404, detail="Patient not found")
    return details


@app.post("/api/patients")
def api_create_patient_route(payload: PatientCreate):
    new_id = create_patient(
        payload.firstName,
        payload.lastName,
        payload.DOB,
        payload.phoneNumber,
        payload.gender,
    )
    return {"patientId": new_id}


@app.post("/api/patients/{patient_id}/notes")
def api_add_note(patient_id: str, payload: KeyNoteCreate):
    note_id = add_key_note(
        patient_id=patient_id,
        note_text=payload.noteText,
        created_by=payload.createdBy,
    )
    return {"noteId": note_id}


@app.post("/api/patients/{patient_id}/priority")
def api_update_priority(patient_id: str, payload: PriorityUpdate):
    set_patient_priority(
        patient_id=patient_id,
        priority_level=payload.priorityLevel,
        priority_status=payload.priorityStatus,
        reason=payload.reason,
        assigned_nurse=payload.assignedNurse,
    )
    return {"status": "ok"}


@app.post("/api/queue/pop-admitted")
def api_pop_admitted():
    removed = pop_admitted_patients_from_queue()
    return {"removed": removed}
