# test_triage.py
from triageService import (
    create_patient,
    add_key_note,
    set_triage_priority,
    get_patient_details
)

def main():
    # 1) create a patient
    patient_id = create_patient(
        first_name="Jane",
        last_name="Doe",
        dob="January 30th, 2000",
        phone_number="123-456-7890",
        gender="Female"
    )
    print("New patient_id:", patient_id)

    # 2) add a key note
    note_id = add_key_note(
        patient_id,
        "Severe penicillin allergy. Use alternative antibiotics.",
        created_by="Nurse Quack"
    )
    print("New note_id:", note_id)

    # 3) set triage priority
    set_triage_priority(
        patient_id,
        priority_level="high",
        priority_status="red",
        reason="Chest pain, SOB, hypotension.",
        assigned_nurse="Nurse Quack"
    )

    # 4) fetch combined details
    details = get_patient_details(patient_id)
    print("Patient details:")
    print(details)

if __name__ == "__main__":
    main()