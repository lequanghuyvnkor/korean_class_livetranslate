import sounddevice as sd
import numpy as np
import threading
import queue
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AudioManager")

class AudioManager:
    def __init__(self, sample_rate=16000, chunk_duration=3.5, silence_threshold=0.015, silence_duration=0.7):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        
        self.stream = None
        self.is_recording = False
        self.is_paused = False
        self.device_index = None
        
        # Audio queues and buffers
        self.raw_audio_queue = queue.Queue()
        self.processed_chunks_queue = queue.Queue()
        self.current_volume_rms = 0.0
        
        self.worker_thread = None
        self._stop_event = threading.Event()
        
    @staticmethod
    def get_input_devices():
        """List all available audio input devices (Microphones, Line-in, Virtual Cables)"""
        devices = []
        try:
            device_list = sd.query_devices()
            default_input = sd.default.device[0]
            for idx, dev in enumerate(device_list):
                if dev.get('max_input_channels', 0) > 0:
                    devices.append({
                        "id": idx,
                        "name": dev.get('name'),
                        "hostapi": dev.get('hostapi'),
                        "channels": dev.get('max_input_channels'),
                        "default_samplerate": dev.get('default_samplerate'),
                        "is_default": (idx == default_input)
                    })
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
        return devices

    def _audio_callback(self, indata, frames, time_info, status):
        """Low-latency callback from SoundDevice stream"""
        if status:
            logger.warning(f"SoundDevice status warning: {status}")
        
        audio_data = indata[:, 0].copy()
        
        # Calculate real-time RMS for UI volume meter
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        self.current_volume_rms = rms
        
        if self.is_recording and not self.is_paused:
            self.raw_audio_queue.put(audio_data)

    def _process_audio_loop(self):
        """Worker thread that accumulates audio and chunks by speech boundaries"""
        audio_buffer = []
        silence_samples = 0
        min_speech_samples = int(self.sample_rate * 1.2) # at least 1.2s to provide semantic context for Korean
        max_chunk_samples = int(self.sample_rate * 6.5) # max 6.5s per sentence chunk
        silence_limit_samples = int(self.sample_rate * self.silence_duration)
        
        while not self._stop_event.is_set():
            try:
                chunk = self.raw_audio_queue.get(timeout=0.1)
                if self.is_paused:
                    audio_buffer = []
                    continue

                audio_buffer.append(chunk)
                
                chunk_rms = np.sqrt(np.mean(chunk ** 2))
                if chunk_rms < self.silence_threshold:
                    silence_samples += len(chunk)
                else:
                    silence_samples = 0
                
                total_samples = sum(len(c) for c in audio_buffer)
                
                should_emit = False
                if total_samples >= min_speech_samples and silence_samples >= silence_limit_samples:
                    should_emit = True
                elif total_samples >= max_chunk_samples:
                    should_emit = True
                    
                if should_emit:
                    full_audio = np.concatenate(audio_buffer).astype(np.float32)
                    audio_buffer = []
                    silence_samples = 0
                    
                    if np.sqrt(np.mean(full_audio ** 2)) > (self.silence_threshold * 0.8):
                        self.processed_chunks_queue.put(full_audio)
                        
            except queue.Empty:
                if len(audio_buffer) > 0 and not self.is_paused:
                    total_samples = sum(len(c) for c in audio_buffer)
                    if total_samples >= min_speech_samples:
                        full_audio = np.concatenate(audio_buffer).astype(np.float32)
                        audio_buffer = []
                        silence_samples = 0
                        if np.sqrt(np.mean(full_audio ** 2)) > (self.silence_threshold * 0.8):
                            self.processed_chunks_queue.put(full_audio)
                continue
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}")

    def start(self, device_index=None):
        """Start listening to microphone"""
        if self.is_recording:
            self.is_paused = False
            return True
            
        self.device_index = device_index
        self._stop_event.clear()
        self.is_paused = False
        
        while not self.raw_audio_queue.empty():
            self.raw_audio_queue.get_nowait()
        while not self.processed_chunks_queue.empty():
            self.processed_chunks_queue.get_nowait()
            
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                device=self.device_index,
                blocksize=int(self.sample_rate * 0.1),
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_recording = True
            
            self.worker_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self.worker_thread.start()
            logger.info(f"Microphone recording started on device: {self.device_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self.is_recording = False
            return False

    def pause(self):
        """Pause listening without closing the stream"""
        self.is_paused = True
        logger.info("Microphone listening paused.")
        return True

    def resume(self):
        """Resume listening"""
        self.is_paused = False
        logger.info("Microphone listening resumed.")
        return True

    def stop(self):
        """Stop listening completely"""
        self.is_recording = False
        self.is_paused = False
        self._stop_event.set()
        
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.warning(f"Error closing stream: {e}")
            self.stream = None
            
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
            
        logger.info("Microphone recording stopped.")
        return True

    def get_audio_chunk(self, timeout=0.2):
        """Get next ready audio chunk for Whisper inference"""
        try:
            return self.processed_chunks_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_rms_level(self):
        """Get current volume RMS value (0.0 to 1.0) for meter"""
        if self.is_paused:
            return 0.0
        return min(1.0, self.current_volume_rms * 10.0)
