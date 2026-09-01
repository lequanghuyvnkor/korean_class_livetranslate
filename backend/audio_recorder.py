import os
import wave
import numpy as np
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AudioRecorder")

class AudioRecorder:
    def __init__(self, base_dir="recordings"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
        self.wave_file = None
        self.current_filepath = None
        self.sample_rate = 16000
        self.is_recording = False

    def start_recording(self, subject_name="General", lecture_title="Lecture"):
        """Start writing continuous audio frames to a WAV file organized by subject"""
        safe_subject = re_sanitize(subject_name)
        safe_title = re_sanitize(lecture_title)
        
        subject_dir = os.path.join(self.base_dir, safe_subject)
        os.makedirs(subject_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_title}.wav"
        self.current_filepath = os.path.join(subject_dir, filename)
        
        try:
            self.wave_file = wave.open(self.current_filepath, "wb")
            self.wave_file.setnchannels(1)        # Mono
            self.wave_file.setsampwidth(2)       # 16-bit PCM
            self.wave_file.setframerate(self.sample_rate)
            self.is_recording = True
            logger.info(f"WAV Audio recording started: {self.current_filepath}")
            return self.current_filepath
        except Exception as e:
            logger.error(f"Failed to open WAV file: {e}")
            self.is_recording = False
            return None

    def write_frames(self, float_audio_chunk: np.ndarray):
        """Write float32 numpy audio chunk as 16-bit PCM bytes"""
        if not self.is_recording or self.wave_file is None:
            return
            
        try:
            # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767]
            pcm16 = (np.clip(float_audio_chunk, -1.0, 1.0) * 32767).astype(np.int16)
            self.wave_file.writeframes(pcm16.tobytes())
        except Exception as e:
            logger.error(f"Error writing audio frames to WAV: {e}")

    def stop_recording(self):
        """Finalize and close WAV file"""
        if self.wave_file:
            try:
                self.wave_file.close()
                logger.info(f"WAV Audio saved successfully to: {self.current_filepath}")
            except Exception as e:
                logger.error(f"Error closing WAV file: {e}")
            self.wave_file = None
            
        self.is_recording = False
        return self.current_filepath

def re_sanitize(text: str) -> str:
    """Sanitize folder and file names"""
    if not text:
        return "General"
    keepcharacters = (' ', '.', '_', '-')
    clean = "".join(c for c in text if c.isalnum() or c in keepcharacters).rstrip()
    return clean.replace(" ", "_") if clean else "General"
