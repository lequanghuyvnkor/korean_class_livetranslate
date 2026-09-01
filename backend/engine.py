import os
import sys
import re
import time
import logging
import numpy as np
from typing import Dict, Any, Optional

# Prevent OpenMP crash on Windows Intel CPU / Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TranslatorEngine")

def clean_repetition(text: str) -> str:
    """Removes annoying Whisper hallucination repetitions (e.g., repeated phrases, prompt echo)"""
    if not text:
        return ""
    text = text.strip()
    
    # Remove identical phrase repetitions like "in the early morning, in the early morning..."
    words = text.split()
    if len(words) > 8:
        # Check if 3-word or 4-word n-gram repeats endlessly
        for n in range(2, 6):
            ngrams = [" ".join(words[i:i+n]) for i in range(len(words)-n+1)]
            if len(ngrams) > 4:
                most_frequent = max(set(ngrams), key=ngrams.count)
                if ngrams.count(most_frequent) >= 3 and len(most_frequent) > 6:
                    # Truncate to just the first occurrence
                    first_idx = text.find(most_frequent)
                    second_idx = text.find(most_frequent, first_idx + len(most_frequent))
                    if second_idx != -1:
                        text = text[:second_idx].strip()
                        break

    # Remove repeated commas / periods / numbers hallucination (e.g. 1,000,000,000...)
    text = re.sub(r'(\b\w+\b)(,\s*\1)+', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(\b\w+\b)(\s+\1){2,}', r'\1', text, flags=re.IGNORECASE)
    return text.strip()

class TranslatorEngine:
    def __init__(self, model_size="base", device="cpu", compute_type="int8", cpu_threads=4):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.model = None
        self.is_loaded = False
        self.initial_prompt = "" # Leave empty by default to prevent hallucination loops
        self.load_model(model_size)

    def load_model(self, model_size="base"):
        """Load or reload Faster-Whisper model (tiny, base, small, turbo, large-v3-turbo)"""
        try:
            logger.info(f"Loading Faster-Whisper model '{model_size}' on {self.device} ({self.compute_type})...")
            from faster_whisper import WhisperModel
            self.model_size = model_size
            
            # Map 'turbo' or 'large-v3-turbo' to deepdml/faster-whisper-large-v3-turbo-ct2 or standard repo
            model_identifier = model_size
            if model_size in ["turbo", "large-v3-turbo"]:
                model_identifier = "deepdml/faster-whisper-large-v3-turbo-ct2"

            self.model = WhisperModel(
                model_size_or_path=model_identifier,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper")
            )
            self.is_loaded = True
            logger.info(f"Model '{model_size}' successfully loaded.")
            return True
        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper model '{model_size}': {e}")
            self.is_loaded = False
            return False

    def set_initial_prompt(self, prompt: str):
        """Update context vocabulary prompt for domain jargon"""
        self.initial_prompt = prompt.strip() if prompt else ""
        logger.info(f"Updated initial prompt: {self.initial_prompt}")

    def process_audio(self, audio_data: np.ndarray, source_lang: str = "ko", target_lang: str = "en") -> Optional[Dict[str, Any]]:
        """
        Process audio segment with anti-hallucination parameters:
        1. condition_on_previous_text=False (prevents carrying over hallucinated tokens)
        2. compression_ratio_threshold=2.2 (filters repetitive gibberish)
        3. no_speech_threshold=0.6 (filters silence/mic noise)
        4. clean_repetition post-processor
        """
        if not self.is_loaded or self.model is None:
            logger.error("Whisper Model not loaded!")
            return None

        if len(audio_data) < 16000 * 0.8: # at least 0.8s
            return None

        # Check RMS energy - if too low, ignore as background noise
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        if rms < 0.008:
            return None

        start_time = time.time()
        
        try:
            # Common Whisper parameters to prevent hallucinations
            whisper_kwargs = dict(
                language=source_lang,
                initial_prompt=self.initial_prompt if self.initial_prompt else None,
                beam_size=2,
                best_of=2,
                temperature=0.0,
                condition_on_previous_text=False, # CRITICAL: stops repetition loops!
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                compression_ratio_threshold=2.2,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0
            )

            # Step 1: Translate directly to English
            trans_segments, _ = self.model.transcribe(
                audio_data,
                task="translate",
                **whisper_kwargs
            )
            english_raw = " ".join([seg.text.strip() for seg in trans_segments if seg.no_speech_prob < 0.7]).strip()
            english_text = clean_repetition(english_raw)

            # Step 2: Transcribe Korean original text
            orig_segments, _ = self.model.transcribe(
                audio_data,
                task="transcribe",
                **whisper_kwargs
            )
            korean_raw = " ".join([seg.text.strip() for seg in orig_segments if seg.no_speech_prob < 0.7]).strip()
            korean_text = clean_repetition(korean_raw)

            elapsed = round(time.time() - start_time, 2)
            
            # Filter if both empty or if it just echoed the initial prompt
            if not korean_text and not english_text:
                return None
                
            if self.initial_prompt and (korean_text == self.initial_prompt or english_text == self.initial_prompt):
                return None

            # Ignore pure punctuation or single characters
            if len(korean_text) < 2 and len(english_text) < 2:
                return None

            # If one is empty, fallback
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
