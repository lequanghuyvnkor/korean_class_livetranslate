import sounddevice as sd
import numpy as np
import time

print("Testing opening default sounddevice input stream...")
def callback(indata, frames, time_info, status):
    rms = np.sqrt(np.mean(indata[:, 0] ** 2))
    print(f"Callback received audio! RMS: {rms:.4f}")

try:
    stream = sd.InputStream(samplerate=16000, channels=1, dtype='float32', callback=callback)
    stream.start()
    print("Stream started successfully! Listening for 1.5 seconds...")
    time.sleep(1.5)
    stream.stop()
    stream.close()
    print("SUCCESS: sounddevice InputStream works flawlessly!")
except Exception as e:
    print("ERROR:", e)
