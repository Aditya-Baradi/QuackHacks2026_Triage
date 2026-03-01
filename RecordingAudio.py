import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

samplerate = 16000
channels = 1

def record_audio(index):
    recording = []
    is_recording = True
    print("Press Enter to start recording...")
    input()

    def callback(indata, frames, time, status):
        if is_recording:
            recording.append(indata.copy())

    with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
        print("Recording... Press Enter to stop.")
        input()

    is_recording = False  # stop recording inside stream context

    # Concatenate frames
    audio = np.concatenate(recording, axis=0)

    # Save file
    filename = f"Recordings/recording{index}.wav"
    write(filename, samplerate, audio)
    print(f"Saved {filename}\n")