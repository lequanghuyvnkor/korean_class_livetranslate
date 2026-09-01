import os
import sys

# Fix Windows Anaconda OpenMP collision crash
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "4"

import webbrowser
import threading
import time
import uvicorn

def open_browser(url: str):
    time.sleep(1.2)
    print(f"Opening browser at: {url}")
    webbrowser.open(url)

def main():
    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    
    print("=" * 65)
    print(" 🇰🇷  KOREAN LIVE LECTURE TRANSLATOR (실시간 강의 번역)  🇬🇧")
    print("=" * 65)
    print(f"[*] Starting local server at: {url}")
    print("[*] Engine: Offline Faster-Whisper (Intel CPU Optimized)")
    print("[*] Features: Real-time Korean -> English, HUD Floating Overlay,")
    print("              Microphone Audio Visualizer, Markdown & SRT Export.")
    print("=" * 65)
    
    # Auto-open browser in a separate thread
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    
    # Run FastAPI app
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
