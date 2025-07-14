from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp as youtube_dl
from typing import Optional
import os
import uuid
from pathlib import Path

app = FastAPI(
    title="YouTube Downloader API",
    description="Download YouTube videos (MP4/MP3)",
    version="1.0.0"
)

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Download directory
DOWNLOAD_FOLDER = "/tmp/downloads"
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

# Cookies file path
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

def sanitize_filename(filename: str) -> str:
    return ''.join(c for c in filename if c not in '<>:"/\\|?*')

def get_video_info(url: str) -> dict:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'cookiefile': COOKIES_FILE,
    }
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Untitled'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'webpage_url': info.get('webpage_url', url),
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching video info: {str(e)}")

def download_youtube_video(url: str, format: str = 'mp4') -> str:
    unique_id = str(uuid.uuid4())
    output_path = f"{DOWNLOAD_FOLDER}/{unique_id}.%(ext)s"

    if format == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'cookiefile': COOKIES_FILE,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': output_path,
            'quiet': True,
        }
    else:  # mp4
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'cookiefile': COOKIES_FILE,
            'outtmpl': output_path,
            'quiet': True,
        }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if format == 'mp3':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            return filename
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error downloading video: {str(e)}")

@app.get("/")
async def root():
    return {"message": "YouTube Downloader API is running"}

@app.get("/info")
async def info(url: str = Query(..., description="YouTube URL")):
    return get_video_info(url)

@app.get("/download")
async def download(
    url: str = Query(..., description="YouTube video URL"),
    format: str = Query("mp4", regex="^(mp3|mp4)$", description="Output format")
):
    video_info = get_video_info(url)
    file_path = download_youtube_video(url, format)
    filename = f"{sanitize_filename(video_info['title'])}.{format}"

    response = FileResponse(
        path=file_path,
        media_type="audio/mpeg" if format == "mp3" else "video/mp4",
        filename=filename
    )

    @response.on_close
    def cleanup():
        try:
            os.remove(file_path)
        except:
            pass

    return response
