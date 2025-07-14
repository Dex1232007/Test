from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import subprocess
import os
import uuid

app = FastAPI()

# Directories
DOWNLOAD_DIR = "downloads"
COOKIES_FILE = "cookies.txt"

# Ensure folder exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Serve static files
app.mount("/files", StaticFiles(directory=DOWNLOAD_DIR), name="files")

@app.get("/")
def home():
    return {"message": "YouTube Downloader API is running."}

@app.get("/download")
def download_video(
    request: Request,
    url: str = Query(..., description="YouTube URL"),
    format: Optional[str] = Query("mp4", description="Format: mp4 or mp3")
):
    # Validate cookies.txt exists
    if not os.path.exists(COOKIES_FILE):
        return JSONResponse(status_code=500, content={"error": "cookies.txt not found on server."})

    # Create unique ID filename
    video_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s")

    # Base yt-dlp command
    cmd = [
        "yt-dlp",
        "--cookies", COOKIES_FILE,
        "-o", output_template,
        url
    ]

    # Format logic
    if format == "mp3":
        cmd += ["--extract-audio", "--audio-format", "mp3"]
    elif format == "mp4":
        cmd += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"]

    # Run yt-dlp
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={
            "error": "Download failed",
            "detail": str(e)
        })

    # Find downloaded file
    for file in os.listdir(DOWNLOAD_DIR):
        if file.startswith(video_id):
            full_url = str(request.base_url) + f"files/{file}"
            return {
                "status": "success",
                "format": format,
                "filename": file,
                "download_url": full_url
            }

    return JSONResponse(status_code=500, content={"error": "File not found"})
