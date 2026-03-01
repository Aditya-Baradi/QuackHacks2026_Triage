# triage_service.py

from datetime import datetime, timedelta

from bson import ObjectId
from db import client, db, keynotes_col, patients_col, triage_priority_col
from pymongo.errors import ServerSelectionTimeoutError

# -------------------------------
# TEST CONNECTION
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


def increment_time(
    base_time: datetime | None = None,
    *,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0,
) -> datetime:
    if base_time is None:
        base_time = datetime.utcnow()

    return base_time + timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _to_object_id(patient_id: str) -> ObjectId:
    try:
        return ObjectId(patient_id)
    except Exception as exc:
        raise ValueError("Invalid patient_id format") from exc


def create_patient(first_name: str, last_name: str, dob: str, phone_number: str, gender: str | None = None) -> str:
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
    oid = _to_object_id(patient_id)

    doc = patients_col.find_one({"_id": oid})
    if not doc:
        return None

    # Convert ObjectId to string for easier JSON usage
    doc["_id"] = str(doc["_id"])
    return doc

def add_key_note(patient_id: str, note_text: str, created_by: str | None = None) -> str:
    oid = _to_object_id(patient_id)

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
    oid = _to_object_id(patient_id)

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

    oid = _to_object_id(patient_id)

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


def get_patient_priority(patient_id: str) -> int | None:
    """
    Return the patient's numeric priority level, or None if no triage record exists.
    """
    oid = _to_object_id(patient_id)
    triage = triage_priority_col.find_one({"patientId": oid}, {"priorityLevel": 1})
    if not triage:
        return None

    try:
        return int(triage["priorityLevel"])
    except (TypeError, ValueError):
        return None


def set_patient_priority(
    patient_id: str,
    priority_level: int,
    priority_status: str = "waiting",
    reason: str | None = None,
    assigned_nurse: str | None = None,
) -> None:
    
    set_triage_priority(
        patient_id=patient_id,
        priority_level=str(priority_level),
        priority_status=priority_status,
        reason=reason,
        assigned_nurse=assigned_nurse,
    )


def pop_admitted_patients_from_queue() -> list[dict]:
    admitted_records = list(triage_priority_col.find({"priorityStatus": "admitted"}))
    if not admitted_records:
        return []

    patient_ids = [record["patientId"] for record in admitted_records]
    triage_priority_col.delete_many({"patientId": {"$in": patient_ids}})

    removed = []
    for record in admitted_records:
        record["_id"] = str(record["_id"])
        record["patientId"] = str(record["patientId"])
        removed.append(record)

    return removed


def sort_patients_by_priority() -> list[dict]:
    queue = []

    for triage in triage_priority_col.find():
        patient_id = str(triage["patientId"])
        details = get_patient_details(patient_id)
        if not details:
            continue

        try:
            numeric_priority = int(triage.get("priorityLevel", 0))
        except (TypeError, ValueError):
            numeric_priority = 0

        details["numericPriority"] = numeric_priority
        queue.append(details)

    queue.sort(key=lambda item: item["numericPriority"], reverse=True)
    return queue
