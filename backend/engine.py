import os
import sys

# Prevent OpenMP crash on Windows Intel CPU / Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import time
import logging

import numpy as np
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TranslatorEngine")

class TranslatorEngine:
    def __init__(self, model_size="base", device="cpu", compute_type="int8", cpu_threads=4):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.model = None
        self.is_loaded = False
        self.initial_prompt = "한국어 대학교 강의, 학술 용어, 수업 내용" # Default Korean lecture context booster
        self.load_model(model_size)

    def load_model(self, model_size="base"):
        """Load or reload Faster-Whisper model"""
        try:
            logger.info(f"Loading Faster-Whisper model '{model_size}' on {self.device} ({self.compute_type})...")
            from faster_whisper import WhisperModel
            self.model_size = model_size
            self.model = WhisperModel(
                model_size_or_path=model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper")
            )
            self.is_loaded = True
            logger.info(f"Model '{model_size}' successfully loaded.")
            return True
        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper model: {e}")
            self.is_loaded = False
            return False

    def set_initial_prompt(self, prompt: str):
        """Update context vocabulary prompt for domain jargon"""
        self.initial_prompt = prompt
        logger.info(f"Updated initial prompt: {prompt}")

    def process_audio(self, audio_data: np.ndarray, source_lang: str = "ko", target_lang: str = "en") -> Optional[Dict[str, Any]]:
        """
        Process audio segment:
        1. Transcribes Original Korean audio
        2. Translates to English
        """
        if not self.is_loaded or self.model is None:
            logger.error("Whisper Model not loaded!")
            return None

        if len(audio_data) < 1600: # less than 0.1s
            return None

        start_time = time.time()
        
        try:
            # Step 1: Translate directly to English
            # Whisper's task='translate' translates any supported language directly into English
            trans_segments, trans_info = self.model.transcribe(
                audio_data,
                language=source_lang,
                task="translate",
                initial_prompt=self.initial_prompt,
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                temperature=0.0
            )
            english_text = " ".join([seg.text.strip() for seg in trans_segments]).strip()

            # Step 2: Transcribe Korean original text
            orig_segments, orig_info = self.model.transcribe(
                audio_data,
                language=source_lang,
                task="transcribe",
                initial_prompt=self.initial_prompt,
                beam_size=2,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                temperature=0.0
            )
            korean_text = " ".join([seg.text.strip() for seg in orig_segments]).strip()

            elapsed = round(time.time() - start_time, 2)
            
            # Filter hallucinations / repetitive blank tokens
            if not korean_text and not english_text:
                return None
                
            # If one is empty, fallback to the other
            if not english_text and korean_text:
                english_text = f"({korean_text})"
            if not korean_text and english_text:
                korean_text = f"({english_text})"

            return {
                "korean": korean_text,
                "english": english_text,
                "duration": round(len(audio_data) / 16000.0, 2),
                "inference_time": elapsed,
                "timestamp": time.strftime("%H:%M:%S")
            }

        except Exception as e:
            logger.error(f"Error during audio inference: {e}")
            return None
