# questions.py

# Section 1 — Immediate Danger Screening
section_1_danger_screening = {
    1: "Are you having trouble breathing right now?",
    2: "Are you having chest pain, pressure, or tightness?",
    3: "Did you faint or lose consciousness today?",
    4: "Are you having new confusion or difficulty speaking?",
    5: "Do you have weakness or numbness on one side of your body?",
    6: "Are you having a seizure now or did you just have one?",
    7: "Are you bleeding heavily and cannot stop it?",
    8: "Are your lips, tongue, or throat swelling?",
    9: "Are you having a severe allergic reaction?",
    10: "Are you thinking about hurting yourself or someone else right now?"
}

# Section 2 — Chief Complaint
section_2_chief_complaint = {
    11: "What brought you in today?",
    12: "When did your symptoms start?",
    13: "Did your symptoms begin suddenly or gradually?",
    14: "Is the problem getting worse, better, or staying the same?",
    15: "Where is the problem located? (Body area)",
    16: "On a scale of 0 to 10, how severe is your pain or discomfort?"
}

# Section 3 — Symptom-Specific Screening
symptoms_chest_heart = {
    17: "Does the pain spread to your arm, jaw, back, or shoulder?",
    18: "Are you sweating, nauseated, or short of breath with it?",
    19: "Have you had this before?"
}

symptoms_breathing = {
    20: "Is it hard to speak full sentences?",
    21: "Does it get worse when lying down?",
    22: "Do you have wheezing or coughing?",
    23: "Do you use oxygen at home?"
}

symptoms_stroke_neuro = {
    24: "Do you have slurred speech?",
    25: "Do you have facial drooping?",
    26: "Do you have trouble walking?",
    27: "Do you have a severe headache that started suddenly?",
    28: "Is this the worst headache of your life?"
}

symptoms_abdominal = {
    29: "Where exactly is the pain?",
    30: "Are you vomiting?",
    31: "Is there blood in your vomit?",
    32: "Do you have diarrhea?",
    33: "Is there blood in your stool?",
    34: "Are you pregnant or could you be pregnant?"
}

symptoms_fever_infection = {
    35: "Do you have a fever?",
    36: "What was your highest temperature?",
    37: "Do you have chills or shaking?",
    38: "Do you have a rash?"
}

symptoms_injury_trauma = {
    39: "What happened?",
    40: "Did you hit your head?",
    41: "Did you lose consciousness?",
    42: "Are you on blood thinners?",
    43: "Can you move the injured area?",
    44: "Is there deformity or severe swelling?"
}

# Section 4 — Risk Factors
section_4_risk_factors = {
    45: "Do you have heart disease?",
    46: "Do you have high blood pressure?",
    47: "Do you have diabetes?",
    48: "Do you have asthma or lung disease?",
    49: "Do you have a history of stroke?",
    50: "Do you have seizures?",
    51: "Do you have cancer?",
    52: "Are you immunocompromised?",
    53: "Have you had recent surgery?",
    54: "Are you currently pregnant?"
}

# Section 5 — Medications & Allergies
section_5_meds_allergies = {
    55: "Are you allergic to any medications?",
    56: "What medications are you currently taking?",
    57: "Are you taking blood thinners?",
    58: "Did you take anything for this problem today?"
}

# Section 6 — Mental Health 
section_6_mental_health = {
    59: "Are you feeling depressed or hopeless?",
    60: "Have you had thoughts of harming yourself?",
    61: "Do you have a plan to harm yourself?",
    62: "Are you hearing or seeing things others do not?",
    63: "Do you feel safe right now?"
}

# Section 7 — Logistics & Context
section_7_logistics = {
    64: "What is your full name?",
    65: "What is your date of birth?",
    66: "What is your preferred language?",
    67: "Do you have someone with you?",
    68: "Is there anything else the nurse should know?"
}

# Voice Analysis Prompts
voice_analysis_prompts = {
    69: "Please describe your symptoms in your own words.",
    70: "Please repeat: 'Today is a sunny day.'",
    71: "Please say the numbers: 4, 7, 2, 9.",
    72: "Please count from 1 to 10."
}