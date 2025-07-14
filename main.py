#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Configuration
DOWNLOAD_DIR = "youtube_downloads"
RATE_LIMIT = 3  # Max downloads per minute per IP
Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

# Rate limiting storage
download_times: Dict[str, list] = {}

def is_valid_youtube_url(url: str) -> bool:
    """Validate YouTube URL with more patterns"""
    patterns = [
        r"^(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^(https?://)?youtu\.be/[\w-]+",
        r"^(https?://)?(www\.)?youtube\.com/shorts/[\w-]+",
        r"^(https?://)?(www\.)?youtube\.com/embed/[\w-]+",
        r"^(https?://)?(www\.)?youtube\.com/live/[\w-]+"
    ]
    return any(re.match(pattern, url) for pattern in patterns)

def check_rate_limit(ip: str) -> bool:
    """Check if IP has exceeded rate limit"""
    now = datetime.now()
    if ip not in download_times:
        download_times[ip] = []
    
    # Remove old timestamps
    download_times[ip] = [t for t in download_times[ip] if now - t < timedelta(minutes=1)]
    
    if len(download_times[ip]) >= RATE_LIMIT:
        return False
    
    download_times[ip].append(now)
    return True

def download_video(url: str, quality: str = "best") -> str:
    """Download video using yt-dlp without cookies"""
    try:
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:skip=webpage",  # Skip webpage check
            "--throttled-rate", "1M",  # Limit download speed
            "--sleep-interval", "10",  # Add delay between requests
            "--max-sleep-interval", "30",
            "--force-ipv4",  # Force IPv4 to avoid some blocks
            "--geo-bypass",  # Bypass geographic restrictions
            "--no-check-certificate",  # Avoid SSL issues
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "-f", f"bestvideo[height<={quality}]+bestaudio/best" if quality != "best" else "best",
            "-o", f"{DOWNLOAD_DIR}/%(title).200s [%(id)s].%(ext)s",
            "--no-playlist",
            "--no-warnings",
            url
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=600,
            check=True
        )
        
        # Find downloaded file
        for line in result.stdout.split('\n'):
            if line.startswith('[download] Destination: '):
                return line.split('[download] Destination: ')[1].strip()
        
        raise Exception("Downloaded file path not found in output")
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or "Unknown error occurred"
        if "HTTP Error 429" in error_msg:
            raise Exception("YouTube is rate limiting us. Please try again later.")
        raise Exception(error_msg)
    except Exception as e:
        raise Exception(f"Download failed: {str(e)}")

@app.get("/download")
async def download_endpoint(request: Request, url: str, quality: str = "720"):
    """Download YouTube video endpoint without cookies"""
    # Validate URL
    if not is_valid_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    # Check rate limit
    client_ip = request.client.host or "unknown"
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} downloads per minute."
        )
    
    try:
        filepath = download_video(url, quality)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="Downloaded file not found")
        
        filename = os.path.basename(filepath)
        return FileResponse(
            filepath,
            media_type="application/octet-stream",
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
