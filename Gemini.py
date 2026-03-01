import tempfile
from dotenv import load_dotenv
import os
from openai import OpenAI
import RecordingAudio
import Questions as q
import json
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play

# Load variables from .env
load_dotenv()
'''
client = ElevenLabs(
    api_key=os.getenv("ELEVEN_LABS_API_KEY")
)

audio = client.text_to_speech.convert(
    text="The first move is what sets everything in motion.",
    voice_id="JBFqnCBsd6RMkjVDRZzb",
    model_id="eleven_multilingual_v2",
    output_format="mp3_44100_128",
)
'''

with open("question_weights.json", "r") as f:
    weights = json.load(f)
def get_weight(question_number, weights_dict):
    return weights_dict.get(str(question_number), 0)

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

urgency = 0

def ask_questions(questions):
    index = 0
    transcript = ""
    for question_num in questions.keys():
        #Add formatted question to prompt
        formatted_question = f"\n\nQuestion: {questions[question_num]}\n"

        #AI Asks question
        response = client.responses.create(model="gpt-5.2", input=(prompt+formatted_question))
        print(response.output_text)

        #Wait for response before asking next question / Record audio response. Press enter to continue
        RecordingAudio.record_audio(index)

        #Pass audio file to Jasmine

        #Receive transcript response to question
        #Run transcript through GPT to determine urgency and next question
        answer_analysis = analyze_urgency(formatted_question, transcript)
        audio_path = f"Recordings/recording{index}.wav"

        match (answer_analysis):
            case "YES":
                print("Answered YES\n")
                urgency += get_weight(question_num, weights)
                print(urgency)
            case "NO":
                print("Answered NO")
            case "UNCLEAR":
                print("Answer was unclear")

        
        """
        with open(audio_path, "rb") as audio_file:
            transcript += formatted_question + "\n"
            transcript += client.audio.transcriptions.create(model="gpt-4o-transcribe", file=audio_file).text
            transcript += "\n" 
        """
        index += 1

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

ask_questions(q.section_1_danger_screening)


#send audio 
#jasmine analysis
#receive transcript
#check transcript to go down flow chart
#check for key words, flag alerts



