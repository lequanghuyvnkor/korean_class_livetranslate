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

# Common Korean History / Lecture Phonetic Mishearing Corrector Dictionary
KOREAN_PHONETIC_CORRECTIONS = {
    r'\b댄서\s*끼\b': '뗀석기',
    r'\b댄서\s*기\b': '뗀석기',
    r'\b댄석기\b': '뗀석기',
    r'\b댄석기\s*로\b': '뗀석기로',
    r'\b숨배\s*찌르게\b': '슴베찌르개',
    r'\b순대\s*찌르개\b': '슴베찌르개',
    r'\b숨배찌르개\b': '슴베찌르개',
    r'\b당\s*군\b': '단군',
    r'\b당군\b': '단군',
    r'\b바죽\b': '가죽',
    r'\b선양하고\b': '사냥하고',
    r'\b주목\s*돋기\b': '주먹도끼',
    r'\b주목도끼\b': '주먹도끼',
    r'\b존돌\b': '잔돌',
    r'\b존돌\s*날\b': '잔돌날',
}

# Hallucinated Subtitle Sentences to Filter Out
HALLUCINATION_BLACKLIST = [
    "thank you for watching",
    "thanks for watching",
    "subtitles by",
    "subscribed to",
    "subscribe to my channel",
    "please subscribe",
    "시청해주셔서 감사합니다",
    "구독과 좋아요",
]

def clean_repetition(text: str) -> str:
    """Removes annoying Whisper hallucination repetitions and YouTube subtitle artifacts"""
    if not text:
        return ""
    text = text.strip()
    
    # Filter YouTube end credits / silence hallucinations
    low_text = text.lower()
    for bad in HALLUCINATION_BLACKLIST:
        if bad in low_text:
            return ""

    # Remove identical phrase repetitions like "in the early morning, in the early morning..."
    words = text.split()
    if len(words) > 8:
        for n in range(2, 6):
            ngrams = [" ".join(words[i:i+n]) for i in range(len(words)-n+1)]
            if len(ngrams) > 4:
                most_frequent = max(set(ngrams), key=ngrams.count)
                if ngrams.count(most_frequent) >= 3 and len(most_frequent) > 6:
                    first_idx = text.find(most_frequent)
                    second_idx = text.find(most_frequent, first_idx + len(most_frequent))
                    if second_idx != -1:
                        text = text[:second_idx].strip()
                        break

    text = re.sub(r'(\b\w+\b)(,\s*\1)+', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(\b\w+\b)(\s+\1){2,}', r'\1', text, flags=re.IGNORECASE)
    return text.strip()

def correct_korean_phonetics(text: str) -> str:
    """Corrects common Korean speech-to-text phonetic mishearings in lectures"""
    if not text:
        return ""
    corrected = text
    for pattern, replacement in KOREAN_PHONETIC_CORRECTIONS.items():
        corrected = re.sub(pattern, replacement, corrected)
    return corrected

class TranslatorEngine:
    def __init__(self, model_size="small", device="cpu", compute_type="int8", cpu_threads=4):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.model = None
        self.is_loaded = False
        self.initial_prompt = ""
        self.load_model(model_size)

    def load_model(self, model_size="small"):
        """Load or reload Faster-Whisper model"""
        try:
            logger.info(f"Loading Faster-Whisper model '{model_size}' on {self.device} ({self.compute_type})...")
            from faster_whisper import WhisperModel
            self.model_size = model_size
            
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
        Process audio segment with sentence-level context and phonetic correction
        """
        if not self.is_loaded or self.model is None:
            logger.error("Whisper Model not loaded!")
            return None

        if len(audio_data) < 16000 * 1.0: # at least 1.0s
            return None

        # Check RMS energy
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        if rms < 0.008:
            return None

        start_time = time.time()
        
        try:
            whisper_kwargs = dict(
                language=source_lang,
                initial_prompt=self.initial_prompt if self.initial_prompt else "한국사, 역사의 기록, 대학교 강의 내용",
                beam_size=3,
                best_of=3,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=450),
                compression_ratio_threshold=2.2,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0
            )

            # Step 1: Transcribe Korean original text
            orig_segments, _ = self.model.transcribe(
                audio_data,
                task="transcribe",
                **whisper_kwargs
            )
            korean_raw = " ".join([seg.text.strip() for seg in orig_segments if seg.no_speech_prob < 0.65]).strip()
            korean_cleaned = clean_repetition(korean_raw)
            korean_text = correct_korean_phonetics(korean_cleaned)

            # Step 2: Translate directly to English
            trans_segments, _ = self.model.transcribe(
                audio_data,
                task="translate",
                **whisper_kwargs
            )
            english_raw = " ".join([seg.text.strip() for seg in trans_segments if seg.no_speech_prob < 0.65]).strip()
            english_text = clean_repetition(english_raw)

            elapsed = round(time.time() - start_time, 2)
            
            if not korean_text and not english_text:
                return None

            # Ignore pure single words or silence noise
            if len(korean_text) < 2 and len(english_text) < 2:
                return None

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
