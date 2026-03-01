import tempfile
from dotenv import load_dotenv
import os
from openai import OpenAI
import RecordingAudio
import Questions as q
import json
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
from main import analyze_audio_file
import triageService as ts
import ast

# Load variables from .env
load_dotenv()

EL_client = ElevenLabs(
    api_key=os.getenv("ELEVEN_LABS_API_KEY")
)

audio = EL_client.text_to_speech.convert(
    text="The first move is what sets everything in motion.",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)


with open("question_weights.json", "r") as f:
    weights = json.load(f)
def get_weight(question_number, weights_dict):
    dict =  weights_dict.get("question_weights", 0) 
    return dict.get(str(question_number), 0)

# Get API key
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)
prompt="""
You are an AI triage assistant modeled after an emergency department intake nurse.

Your role is to gather information and assess urgency, NOT diagnose or treat.

Goals:
- Ask one focused question at a time.
- Follow a structured triage approach.

Safety Rules:
- MANDATORY: ONLY say exactly what the question is, do not add any additional information or context.
- MANDATORY: Never diagnose.
- MANDATORY: Never say or affirm that the patient is "fine" or "not serious."
- MANDATORY: Never prescribe medication.
- MANDATORY: Never claim certainty.
- MANDATORY:If emergency symptoms appear, immediately instruct the user to seek emergency services.
- MANDATORY: ONLY ask the questions you are being told to ask.
- MANDATORY: IF ANY RESPONSE INDICATES THAT THE PATIENT IS BLEEDING, HAS HAD A SEIZURE
, CHEST PAIN OR PRESSURE, ARM WEAKNESS, SEVERE ALLEGRIC REACTION, STOP ALL INSTRUCTION AND TRIGGER AN ALARM BY SAYING ALARM.

Communication Style:
- Calm
- Supportive
- Clear
- Neutral

Ask the question listed below.


"""
introduction = """
Begin by introducing yourself with this intro say nothing else:
'Hello, I am your AI triage assistant. I am going to ask a few questions to help the nursing staff. 
If you are feeling worse or are experiencing emergency symptoms, please inform staff immediately.
Let's get started. Please answer the following questions to the best of your ability.
Answer each question by hitting the record button and stop button after your response.'
"""
response = client.responses.create(model="gpt-5.2", input=introduction)
print(response.output_text)

master_transcript = ""
urgency = 0
pathway = 0
affirmative_responses = []

def ask_questions(questions):
    index = 0
    transcript = ""
    for question_num in questions.keys():
        #Add formatted question to prompt
        formatted_question = f"\n\nQuestion: {questions[question_num]}\n"

        #AI Asks question
        response = client.responses.create(model="gpt-5.2", input=(prompt+formatted_question))
        print(response.output_text)
        audio = EL_client.text_to_speech.convert(
        text= response.output_text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

        #Wait for response before asking next question / Record audio response. Press enter to continue
        audio_path = RecordingAudio.record_audio(index)

        #Pass audio file to Jasmine
        analysis_path, transcript_path = analyze_audio_file(
            input_audio=audio_path,
            patient_id="auto_patient",
            session_id=None,  # auto-generates
            question_text="What is your name?",
            was_repeat=False,
            repeat_reason=""
        )

        #Receive transcript response to question
        #Run transcript through GPT to determine urgency and next question

        with open(transcript_path, "r") as file:
            content = file.read()
        
        if(question_num == 16):
            answer_analysis = analyze_Pain(formatted_question, content)
            global urgency
            urgency += int(answer_analysis)  # Add pain score to urgency
        elif(question_num == 11):
            answer_analysis = analyze_Sypmtoms(formatted_question, content)
            global pathway
            pathway = int(answer_analysis)  # Set pathway based on symptoms
        else:
            answer_analysis = analyze_urgency(formatted_question, content)

            match (answer_analysis):
                case "YES":
                    print("Answered YES\n")
                    affirmative_responses.append(question_num)
                    print(f"NUM: {question_num}")
                    urgency += get_weight(question_num, weights)
                    print(urgency)
                case "NO":
                    print("Answered NO")
                case "UNCLEAR":
                    print("Answer was unclear")

        if (urgency >= 100):
            print("ALARM: Urgency threshold exceeded. Immediate attention required.")
            break
        index += 1
        global master_transcript
        master_transcript += f"{formatted_question}\n"
        master_transcript += f"outputs\\patient_auto_patient\\session_session_20260301\\q{index}_transcript.txt\n"

def analyze_urgency(question,response):
    #Use GPT to analyze transcript and determine urgency and next questions
    analyze_prompt = f"""
        You are an AI triage assistant modeled after an emergency department intake nurse.

        Your role is to gather information and assess urgency, NOT diagnose or treat.

        Take this response and simply answer YES if the patient answered the question in the affirmative/yes/positive 
        or NO if the patient answered in the negative/no/negative. Do not add any additional information or context.
        If the response is unclear or ambiguous, answer UNCLEAR.

        Question: {question}
        Response: {response}
    """
    analysis = client.responses.create(model="gpt-5.2", input=analyze_prompt)
    return analysis.output_text.strip()

def analyze_Pain(question,response):
    #Use GPT to analyze transcript and determine urgency and next questions
    analyze_prompt = f"""
        You are an AI triage assistant modeled after an emergency department intake nurse.

        Your role is to gather information and assess urgency, NOT diagnose or treat.

        Take this response and simply answer with a 0, 5, 10, 15, or UNCLEAR based on the patient's description of their pain.
        0 = no pain or minimal pain, if they rate themselves a 0-3
        5 = mild pain, if they rate themselves a 4-6
        10 = moderate pain, if they rate themselves a 7-8
        15 = severe pain, if they rate themselves a 9-10            

        Question: {question}
        Response: {response}
    """
    analysis = client.responses.create(model="gpt-5.2", input=analyze_prompt)
    return analysis.output_text.strip()

def analyze_Sypmtoms(question,response):
    #Use GPT to analyze transcript and determine urgency and next questions
    analyze_prompt = f"""
        You are an AI triage assistant modeled after an emergency department intake nurse.

        Your role is to gather information and assess urgency, NOT diagnose or treat.

        Take this response and simply answer with a number from 1-6.          
            1 = chest or heart sypmtoms
            2 = breathing symptoms
            3 = stroke neuro symptoms
            4 = abdominal symptoms
            5 = fever infection symptoms
            6 = injury trauma symptoms

        Question: {question}
        Response: {response}
    """
    analysis = client.responses.create(model="gpt-5.2", input=analyze_prompt)
    return analysis.output_text.strip()

def analyze_Logistics(transcript):
    #Use GPT to analyze transcript and determine urgency and next questions
    analyze_prompt = f"""
        You are an AI triage assistant modeled after an emergency department intake nurse.

        Your role is to gather information and assess urgency, NOT diagnose or treat.

        Take this transcript and return to me an array of the following demographic information:
        First Name, Last Name, Date of Birth, Phone Number, Sex

        format the response as an array in this format:
        ["First Name", "Last Name", "Date of Birth", "Phone Number", "Sex"]
        Only return the array and nothing else. Do not add any additional information or context.
    """
    analysis = client.responses.create(model="gpt-5.2", input=analyze_prompt)
    return analysis.output_text.strip()

def analyze_Master_Transcript(transcript):
    #Use GPT to analyze transcript and determine urgency and next questions
    analyze_prompt = f"""
        You are an AI triage assistant modeled after an emergency department intake nurse.

        Your role is to gather information and assess urgency, NOT diagnose or treat.

        Take this transcript and summarize the patient's conversation with you.
        Extract any relevany information that could be helpful for the nursing staff
        to know when the patient arrives. This could include information about their symptoms, 
        their living situation, their support system, or any other information that could 
        be helpful for the nursing staff to know when the patient arrives. 
        Create short key words or phrases and return them in a list comma seperated.
        Example: "Has chest pain, Has heart condition, has allergies"
    """
    analysis = client.responses.create(model="gpt-5.2", input=analyze_prompt)
    return analysis.output_text.strip()

ask_questions(q.section_7_logistics)
info = analyze_Logistics(master_transcript) 
info_list = ast.literal_eval(info) 
PID = ts.create_patient(info_list[0], info_list[1], info_list[2], info_list[3], info_list[4])

ask_questions(q.section_1_danger_screening)
ask_questions(q.section_2_chief_complaint)
match (pathway):
    case 1:
        ask_questions(q.symptoms_chest_heart)
    case 2:
        ask_questions(q.symptoms_breathing)
    case 3:
        ask_questions(q.symptoms_stroke_neuro)
    case 4:
        ask_questions(q.symptoms_abdominal)
    case 5:
        ask_questions(q.symptoms_fever_infection) 
    case 6:
        ask_questions(q.symptoms_injury_trauma)   
ask_questions(q.section_4_risk_factors)
ask_questions(q.section_5_meds_allergies)
ask_questions(q.section_6_mental_health)
ask_questions(q.voice_analysis_prompts)

if((34 in affirmative_responses) and (16 in affirmative_responses)):
    urgency += 15
elif ((40 in affirmative_responses) and (42 in affirmative_responses)):
    urgency += 25
elif ((35 in affirmative_responses) and (38 in affirmative_responses)):
    urgency += 10
if urgency >= 100:
    print("ALARM: Urgency threshold exceeded. Immediate attention required.")
elif urgency >= 85:
    status = "Red"
elif urgency >= 40:
    status = "Yellow"
else:
    status = "Green"



ts.set_patient_priority(PID, urgency, status,)

key_notes = analyze_Master_Transcript(master_transcript)

ts.add_key_note(PID, key_notes, created_by="AI Triage Assistant")

#send audio 
#jasmine analysis
#receive transcript
#check transcript to go down flow chart
#check for key words, flag alerts



