#!/usr/bin/env python3
# FastAPI Version (No Flask)

import os
import re
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI()

# Config
DOWNLOAD_DIR = "youtube_downloads"
Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

def is_valid_youtube_url(url: str) -> bool:
    pattern = r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/.+"
    return re.match(pattern, url) is not None

def download_video(url: str, quality: str = "best") -> str:
    try:
        cmd = [
            "yt-dlp",
            "-f", f"bestvideo[height<={quality}]+bestaudio/best" if quality != "best" else "best",
            "-o", f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            "--no-playlist",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('[download] Destination: '):
                    return line.split('[download] Destination: ')[1].strip()
        raise Exception(result.stderr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download")
async def download_endpoint(url: str, quality: str = "1080"):
    if not is_valid_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    try:
        filepath = download_video(url, quality)
        filename = os.path.basename(filepath)
        return FileResponse(
            filepath,
            media_type="application/octet-stream",
            filename=filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
