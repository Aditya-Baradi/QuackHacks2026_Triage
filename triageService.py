# triage_service.py

from datetime import datetime

from bson import ObjectId
from db import client, db, keynotes_col, patients_col, triage_priority_col
from pymongo.errors import ServerSelectionTimeoutError

# -------------------------------
# 2. TEST CONNECTION
# -------------------------------
try:
    # ping the server
    client.admin.command("ping")
    print("Successfully connected to MongoDB Atlas!")
except ServerSelectionTimeoutError as e:
    print("Failed to connect to MongoDB Atlas.")
    print("TLS/network connection failed.")
    print("Check Atlas IP allowlist, disable VPN or antivirus TLS inspection, and verify the cluster is running.")
    print("Details:", e)
except Exception as e:
    print("Failed to connect to MongoDB")
    print("Error:", e)


def create_patient(first_name: str, last_name: str, dob: str, phone_number: str, gender: str | None = None) -> str:
    """
    Create a new patient and return the inserted _id as a string.
    dob: keep as string for now (e.g., 'January 30th, 2000') to match your validator.
    """
    doc = {
        "firstName": first_name,
        "lastName": last_name,
        "DOB": dob,
        "phoneNumber": phone_number,
        "gender": gender,
        "createdAt": datetime.utcnow(),
    }

    result = patients_col.insert_one(doc)
    return str(result.inserted_id)

def get_patient(patient_id: str) -> dict | None:
    """
    Retrieve a single patient document by its _id (as string).
    """
    try:
        oid = ObjectId(patient_id)
    except Exception:
        raise ValueError("Invalid patient_id format")

    doc = patients_col.find_one({"_id": oid})
    if not doc:
        return None

    # Convert ObjectId to string for easier JSON usage
    doc["_id"] = str(doc["_id"])
    return doc

def add_key_note(patient_id: str, note_text: str, created_by: str | None = None) -> str:
    """
    Add an important note to keyNotes for a given patient.
    """
    try:
        oid = ObjectId(patient_id)
    except Exception:
        raise ValueError("Invalid patient_id format")

    doc = {
        "patientId": oid,
        "noteText": note_text,
        "createdAt": datetime.utcnow(),
        "createdBy": created_by,
    }

    result = keynotes_col.insert_one(doc)
    return str(result.inserted_id)

def set_triage_priority(
    patient_id: str,
    priority_level: str,
    priority_status: str,
    reason: str | None = None,
    assigned_nurse: str | None = None
) -> None:
    """
    Upsert the triage priority for a patient.
    priority_status must be one of: 'green', 'yellow', 'red' (enforced by Mongo validator).
    """
    try:
        oid = ObjectId(patient_id)
    except Exception:
        raise ValueError("Invalid patient_id format")

    update_doc = {
        "patientId": oid,
        "priorityLevel": priority_level,
        "priorityStatus": priority_status,
        "reason": reason,
        "assignedNurse": assigned_nurse,
        "lastUpdated": datetime.utcnow(),
    }

    triage_priority_col.update_one(
        {"patientId": oid},
        {"$set": update_doc},
        upsert=True,
    )


def get_patient_details(patient_id: str) -> dict | None:
    """
    Return a combined view:
    {
    "patient": {...},
    "keyNotes": [...],
    "triagePriority": {... or None}
    }
    """
    patient = get_patient(patient_id)
    if not patient:
        return None

    oid = ObjectId(patient_id)

    # Fetch notes
    notes_cursor = keynotes_col.find({"patientId": oid}).sort("createdAt", -1)
    notes = []
    for n in notes_cursor:
        n["_id"] = str(n["_id"])
        n["patientId"] = str(n["patientId"])
        notes.append(n)

    # Fetch triage priority
    triage = triage_priority_col.find_one({"patientId": oid})
    if triage:
        triage["_id"] = str(triage["_id"])
        triage["patientId"] = str(triage["patientId"])

    return {
        "patient": patient,
        "keyNotes": notes,
        "triagePriority": triage,
    }
