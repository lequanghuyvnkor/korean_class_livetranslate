import numpy as np
import threading
import queue
import time
import logging
import soundcard as sc
import sounddevice as sd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AudioManager")

class AudioManager:
    def __init__(self, sample_rate=16000, min_chunk_seconds=3.5, max_chunk_seconds=7.0, silence_threshold=0.015, silence_duration=0.6):
        self.sample_rate = sample_rate
        self.min_chunk_seconds = min_chunk_seconds
        self.max_chunk_seconds = max_chunk_seconds
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        
        self.is_recording = False
        self.is_paused = False
        self.device_id = None
        
        # Audio queues
        self.raw_audio_queue = queue.Queue()
        self.processed_chunks_queue = queue.Queue()
        self.current_volume_rms = 0.0
        
        self.capture_thread = None
        self.process_thread = None
        self._stop_event = threading.Event()
        
    @staticmethod
    def get_input_devices():
        """List all available audio input devices (Physical Mics + System Audio Loopback)"""
        devices = []
        try:
            # 1. Soundcard loopback & hardware devices
            all_mics = sc.all_microphones(include_loopback=True)
            for idx, mic in enumerate(all_mics):
                display_name = mic.name
                if mic.isloopback:
                    display_name = f"🔊 [System Audio Loopback] {mic.name} (Âm thanh trong máy/Youtube/Zoom)"
                else:
                    display_name = f"🎙️ [Microphone] {mic.name}"
                    
                devices.append({
                    "id": mic.id,
                    "name": display_name,
                    "is_loopback": mic.isloopback,
                    "is_default": (idx == 0)
                })
        except Exception as e:
            logger.error(f"Error querying devices with soundcard: {e}")
            # Fallback to sounddevice
            try:
                for idx, dev in enumerate(sd.query_devices()):
                    if dev.get('max_input_channels', 0) > 0:
                        devices.append({
                            "id": str(idx),
                            "name": dev.get('name'),
                            "is_loopback": False,
                            "is_default": (idx == sd.default.device[0])
                        })
            except Exception as e2:
                logger.error(f"Fallback sounddevice failed: {e2}")
                
        return devices

    def _capture_audio_worker(self, device_id):
        """Low-latency capture loop using soundcard recorder"""
        try:
            if device_id:
                mic = sc.get_microphone(id=device_id, include_loopback=True)
            else:
                # Default to loopback speaker or default mic
                all_mics = sc.all_microphones(include_loopback=True)
                mic = all_mics[0] if len(all_mics) > 0 else sc.default_microphone()

            logger.info(f"Started soundcard audio capture on: {mic.name} (loopback={mic.isloopback})")
            
            block_frames = int(self.sample_rate * 0.1) # 100ms blocks
            
            with mic.recorder(samplerate=self.sample_rate, channels=1, blocksize=block_frames) as recorder:
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=block_frames)
                    if data is None or len(data) == 0:
                        continue
                        
                    audio_1d = data[:, 0].astype(np.float32)
                    
                    # Calculate real-time RMS for UI volume meter
                    rms = float(np.sqrt(np.mean(audio_1d ** 2)))
                    self.current_volume_rms = rms
                    
                    if self.is_recording and not self.is_paused:
                        self.raw_audio_queue.put(audio_1d)
                        
        except Exception as e:
            logger.error(f"Error in capture worker: {e}")
            # Fallback to standard sounddevice if soundcard fails
            self._fallback_sounddevice_capture(device_id)

    def _fallback_sounddevice_capture(self, device_id):
        """Fallback stream with sounddevice"""
        logger.info("Using fallback sounddevice stream...")
        try:
            dev_idx = None
            if device_id and device_id.isdigit():
                dev_idx = int(device_id)
                
            def sd_cb(indata, frames, time_info, status):
                audio_1d = indata[:, 0].copy()
                self.current_volume_rms = float(np.sqrt(np.mean(audio_1d ** 2)))
                if self.is_recording and not self.is_paused:
                    self.raw_audio_queue.put(audio_1d)
                    
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32', device=dev_idx, blocksize=int(self.sample_rate * 0.1), callback=sd_cb):
                while not self._stop_event.is_set():
                    time.sleep(0.05)
        except Exception as err:
            logger.error(f"Fallback sounddevice failed: {err}")

    def _process_audio_loop(self):
        """Accumulate into grammatically complete Korean sentence chunks"""
        audio_buffer = []
        silence_samples = 0
        min_speech_samples = int(self.sample_rate * self.min_chunk_seconds) # 3.5s minimum
        max_chunk_samples = int(self.sample_rate * self.max_chunk_seconds) # 7.0s max
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
                    
                    if np.sqrt(np.mean(full_audio ** 2)) > (self.silence_threshold * 0.7):
                        self.processed_chunks_queue.put(full_audio)
                        
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}")

    def start(self, device_id=None):
        """Start listening"""
        if self.is_recording:
            self.is_paused = False
            return True
            
        self.device_id = device_id
        self._stop_event.clear()
        self.is_paused = False
        
        while not self.raw_audio_queue.empty():
            self.raw_audio_queue.get_nowait()
        while not self.processed_chunks_queue.empty():
            self.processed_chunks_queue.get_nowait()
            
        self.is_recording = True
        
        self.capture_thread = threading.Thread(target=self._capture_audio_worker, args=(device_id,), daemon=True)
        self.capture_thread.start()
        
        self.process_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
        self.process_thread.start()
        
        logger.info(f"Audio capture started on device_id: {device_id}")
        return True

    def pause(self):
        """Pause listening"""
        self.is_paused = True
        logger.info("Listening paused.")
        return True

    def resume(self):
        """Resume listening"""
        self.is_paused = False
        logger.info("Listening resumed.")
        return True

    def stop(self):
        """Stop listening completely"""
        self.is_recording = False
        self.is_paused = False
        self._stop_event.set()
        
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=1.0)
            
        logger.info("Audio recording stopped.")
        return True

    def get_audio_chunk(self, timeout=0.2):
        """Get next ready audio chunk for Whisper inference"""
        try:
            return self.processed_chunks_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_rms_level(self):
        """Get current volume RMS value (0.0 to 1.0) for visual meter"""
        if self.is_paused:
            return 0.0
        return min(1.0, self.current_volume_rms * 10.0)
