import os
import sys

# Prevent OpenMP crash on Windows Intel CPU / Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "4"

import asyncio
import json
import logging
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .audio_manager import AudioManager
from .engine import TranslatorEngine
from .session_logger import SessionLogger
from .audio_recorder import AudioRecorder
from .subject_manager import SubjectManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AppServer")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
DATA_DIR = os.path.join(BASE_DIR, "data")

app = FastAPI(title="Korean Live Lecture Translator & Study Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core services
audio_mgr = AudioManager()
engine = TranslatorEngine(model_size="small")
logger_mgr = SessionLogger(base_transcripts_dir=TRANSCRIPTS_DIR)
recorder_mgr = AudioRecorder(base_dir=RECORDINGS_DIR)
subject_mgr = SubjectManager(data_dir=DATA_DIR, transcripts_dir=TRANSCRIPTS_DIR, recordings_dir=RECORDINGS_DIR)

active_websockets: Set[WebSocket] = set()
translation_task = None
is_processing_active = False

async def broadcast(message: dict):
    """Send JSON message to all connected UI clients"""
    if not active_websockets:
        return
    text = json.dumps(message)
    disconnected = set()
    for ws in active_websockets:
        try:
            await ws.send_text(text)
        except Exception:
            disconnected.add(ws)
    active_websockets.difference_update(disconnected)

async def audio_processing_worker():
    """Continuous async loop that receives audio chunks from microphone and performs translation"""
    global is_processing_active
    loop = asyncio.get_event_loop()
    
    logger.info("Background audio processing worker started.")
    while is_processing_active:
        chunk = await loop.run_in_executor(None, audio_mgr.get_audio_chunk, 0.1)
        
        rms = audio_mgr.get_rms_level()
        await broadcast({
            "type": "volume_level",
            "level": rms,
            "is_recording": audio_mgr.is_recording
        })
        
        if chunk is not None and len(chunk) > 0:
            # Write frames to WAV recording file
            recorder_mgr.write_frames(chunk)
            
            await broadcast({"type": "status", "status": "translating"})
            
            result = await loop.run_in_executor(None, engine.process_audio, chunk, "ko", "en")
            
            if result:
                entry = logger_mgr.add_entry(result)
                await broadcast({
                    "type": "translation",
                    "entry": entry
                })
                
            await broadcast({"type": "status", "status": "listening"})
            
        await asyncio.sleep(0.05)
    logger.info("Background audio processing worker stopped.")

@app.on_event("startup")
async def startup_event():
    logger.info("Server starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    global is_processing_active
    is_processing_active = False
    audio_mgr.stop()
    recorder_mgr.stop_recording()

@app.get("/api/devices")
def get_devices():
    """List available microphones"""
    devices = AudioManager.get_input_devices()
    return {"devices": devices, "current_device": audio_mgr.device_index, "is_recording": audio_mgr.is_recording}

@app.post("/api/open_sound_settings")
def open_sound_settings():
    """Open Windows Sound Control Panel (mmsys.cpl) for user to enable Stereo Mix easily"""
    try:
        import subprocess
        subprocess.Popen(["control", "mmsys.cpl", ",1"])
        return {"status": "success", "message": "Opened Windows Sound Settings"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/start")
async def start_recording(payload: dict = Body(default={})):
    """Start listening to specified microphone and start recording WAV file"""
    global translation_task, is_processing_active
    raw_device_id = payload.get("device_id", None)
    subject_name = payload.get("subject", "General")
    lecture_title = payload.get("title", "Lecture")
    
    device_id = None
    if raw_device_id is not None and str(raw_device_id).isdigit():
        device_id = int(raw_device_id)
        
    # Start audio stream
    success = audio_mgr.start(device_index=device_id)
    if not success:
        raise HTTPException(status_code=500, detail="Could not access selected microphone.")
        
    # Start session and WAV recording
    logger_mgr.start_new_session(title=lecture_title, subject_name=subject_name)
    recorder_mgr.start_recording(subject_name=subject_name, lecture_title=lecture_title)
    
    is_processing_active = True
    if translation_task is None or translation_task.done():
        translation_task = asyncio.create_task(audio_processing_worker())
        
    await broadcast({
        "type": "state_change",
        "is_recording": True,
        "is_paused": False,
        "device_id": device_id,
        "subject": subject_name,
        "title": lecture_title
    })
    return {"status": "started", "device_id": device_id}

@app.post("/api/pause")
async def pause_recording():
    """Pause listening"""
    audio_mgr.pause()
    await broadcast({"type": "state_change", "is_recording": True, "is_paused": True})
    return {"status": "paused"}

@app.post("/api/resume")
async def resume_recording():
    """Resume listening"""
    audio_mgr.resume()
    await broadcast({"type": "state_change", "is_recording": True, "is_paused": False})
    return {"status": "resumed"}

@app.post("/api/stop")
async def stop_recording():
    """Stop listening and save WAV recording"""
    global is_processing_active
    is_processing_active = False
    audio_mgr.stop()
    wav_path = recorder_mgr.stop_recording()
    await broadcast({"type": "state_change", "is_recording": False, "is_paused": False})
    return {"status": "stopped", "wav_file": wav_path}

@app.post("/api/bookmark/last")
async def bookmark_last():
    """Bookmark the last translated sentence"""
    entry = logger_mgr.bookmark_last_entry()
    if entry:
        await broadcast({"type": "bookmark_update", "entry": entry})
        return {"status": "success", "entry": entry}
    return {"status": "none"}

@app.post("/api/bookmark/{entry_id}")
async def toggle_bookmark(entry_id: int):
    """Toggle bookmark on a specific sentence"""
    is_bookmarked = logger_mgr.toggle_bookmark(entry_id)
    await broadcast({"type": "bookmark_toggle", "id": entry_id, "is_bookmark": is_bookmarked})
    return {"status": "success", "id": entry_id, "is_bookmark": is_bookmarked}

@app.get("/api/subjects")
def get_subjects():
    """List all subjects/courses"""
    return {"subjects": subject_mgr.get_all_subjects()}

@app.post("/api/subjects")
def add_subject(payload: dict = Body(...)):
    """Create or update a subject"""
    name = payload.get("name", "")
    glossary = payload.get("glossary", "")
    color = payload.get("color", "#06b6d4")
    sub = subject_mgr.add_subject(name, glossary, color)
    return {"status": "success", "subject": sub}

@app.get("/api/lectures")
def get_lectures():
    """List all past recorded lectures grouped by subject"""
    lectures = subject_mgr.list_all_lectures()
    return {"lectures": lectures}

@app.get("/api/audio/{subject}/{filename}")
def get_audio_file(subject: str, filename: str):
    """Stream WAV audio file for web audio player"""
    filepath = os.path.join(RECORDINGS_DIR, subject, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(filepath, media_type="audio/wav")

@app.get("/api/download_md/{subject}/{filename}")
def download_md(subject: str, filename: str):
    """Download Markdown transcript"""
    filepath = os.path.join(TRANSCRIPTS_DIR, subject, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Markdown file not found")
    return FileResponse(filepath, filename=filename)

@app.post("/api/model")
def change_model(payload: dict = Body(...)):
    """Change Whisper model size (tiny, base, small, turbo)"""
    model_size = payload.get("model_size", "small")
    success = engine.load_model(model_size)
    return {"status": "success" if success else "failed", "current_model": engine.model_size}

@app.post("/api/prompt")
def set_prompt(payload: dict = Body(...)):
    """Set custom domain vocabulary / prompt"""
    prompt = payload.get("prompt", "")
    engine.set_initial_prompt(prompt)
    return {"status": "success", "prompt": engine.initial_prompt}

@app.post("/api/session/new")
def new_session(payload: dict = Body(default={})):
    """Start a new clean lecture session"""
    title = payload.get("title", "")
    subject = payload.get("subject", "General")
    logger_mgr.start_new_session(title=title, subject_name=subject)
    return {"status": "success", "session_id": logger_mgr.session_id, "title": logger_mgr.lecture_title, "subject": logger_mgr.subject_name}

@app.get("/api/session/history")
def get_session_history():
    """Get history entries of current session"""
    return {
        "session_id": logger_mgr.session_id,
        "title": logger_mgr.lecture_title,
        "subject": logger_mgr.subject_name,
        "entries": logger_mgr.get_history()
    }

@app.post("/api/session/export/markdown")
def export_markdown():
    """Export current session to Markdown"""
    filepath = logger_mgr.export_markdown()
    filename = os.path.basename(filepath)
    return {
        "status": "success",
        "filepath": filepath,
        "filename": filename,
        "download_url": f"/api/download_md/{logger_mgr.subject_name}/{filename}"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSockets connection for live translation stream"""
    await websocket.accept()
    active_websockets.add(websocket)
    
    try:
        await websocket.send_text(json.dumps({
            "type": "init",
            "is_recording": audio_mgr.is_recording,
            "is_paused": audio_mgr.is_paused,
            "model_size": engine.model_size,
            "initial_prompt": engine.initial_prompt,
            "lecture_title": logger_mgr.lecture_title,
            "subject": logger_mgr.subject_name,
            "history": logger_mgr.get_history()
        }))
        
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
    except Exception:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# Mount frontend directory
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
