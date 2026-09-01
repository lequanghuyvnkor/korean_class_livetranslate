import os
import sys

# Prevent OpenMP crash on Windows Intel CPU / Anaconda
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AppServer")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")

app = FastAPI(title="Korean Live Lecture Translator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core services
audio_mgr = AudioManager()
engine = TranslatorEngine(model_size="base")
logger_mgr = SessionLogger(export_dir=TRANSCRIPTS_DIR)

# Connected WebSocket clients
active_websockets: Set[WebSocket] = set()

# Background translation worker task
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
        # Check audio chunk from AudioManager
        # Run blocking queue get and inference in executor thread to keep FastAPI responsive
        chunk = await loop.run_in_executor(None, audio_mgr.get_audio_chunk, 0.1)
        
        # Also broadcast current volume RMS level for real-time waveform visualizer
        rms = audio_mgr.get_rms_level()
        await broadcast({
            "type": "volume_level",
            "level": rms,
            "is_recording": audio_mgr.is_recording
        })
        
        if chunk is not None and len(chunk) > 0:
            # Emit live 'processing' state
            await broadcast({"type": "status", "status": "translating"})
            
            # Run Whisper translation in worker thread
            result = await loop.run_in_executor(None, engine.process_audio, chunk, "ko", "en")
            
            if result:
                # Add to session log
                entry = logger_mgr.add_entry(result)
                # Broadcast translation to all HUDs & Dashboards
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
    """Start listening to specified or default microphone"""
    global translation_task, is_processing_active
    raw_device_id = payload.get("device_id", None)
    
    device_id = None
    if raw_device_id is not None and str(raw_device_id).isdigit():
        device_id = int(raw_device_id)
    
    success = audio_mgr.start(device_index=device_id)
    if not success:
        raise HTTPException(status_code=500, detail="Could not access selected microphone.")
        
    is_processing_active = True
    if translation_task is None or translation_task.done():
        translation_task = asyncio.create_task(audio_processing_worker())
        
    await broadcast({"type": "state_change", "is_recording": True, "device_id": device_id})
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
    """Stop listening"""
    global is_processing_active
    is_processing_active = False
    audio_mgr.stop()
    await broadcast({"type": "state_change", "is_recording": False, "is_paused": False})
    return {"status": "stopped"}

@app.post("/api/model")
def change_model(payload: dict = Body(...)):
    """Change Whisper model size (tiny, base, small, medium)"""
    model_size = payload.get("model_size", "base")
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
    logger_mgr.start_new_session(title)
    return {"status": "success", "session_id": logger_mgr.session_id, "title": logger_mgr.lecture_title}

@app.get("/api/session/history")
def get_session_history():
    """Get history entries of current session"""
    return {
        "session_id": logger_mgr.session_id,
        "title": logger_mgr.lecture_title,
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
        "download_url": f"/api/download/{filename}"
    }

@app.post("/api/session/export/srt")
def export_srt():
    """Export current session to SRT"""
    filepath = logger_mgr.export_srt()
    filename = os.path.basename(filepath)
    return {
        "status": "success",
        "filepath": filepath,
        "filename": filename,
        "download_url": f"/api/download/{filename}"
    }

@app.get("/api/download/{filename}")
def download_file(filename: str):
    """Download exported transcript file"""
    filepath = os.path.join(TRANSCRIPTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, filename=filename)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSockets connection for live translation stream"""
    await websocket.accept()
    active_websockets.add(websocket)
    
    # Send initial state & existing history
    try:
        await websocket.send_text(json.dumps({
            "type": "init",
            "is_recording": audio_mgr.is_recording,
            "model_size": engine.model_size,
            "initial_prompt": engine.initial_prompt,
            "lecture_title": logger_mgr.lecture_title,
            "history": logger_mgr.get_history()
        }))
        
        while True:
            data = await websocket.receive_text()
            # Handle client-side commands if any
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
