from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import yt_dlp as youtube_dl
import os
import uuid
from pathlib import Path
import shutil

app = FastAPI(
    title="YouTube Downloader API",
    description="API for downloading YouTube videos as MP4 or MP3",
    version="1.0.0"
)

# CORS settings to allow all origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration for downloads
DOWNLOAD_FOLDER = "/tmp/downloads"
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename

def get_video_info(url: str) -> dict:
    """Get video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
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
    """Download YouTube video and return the file path"""
    unique_id = str(uuid.uuid4())
    
    if format == 'mp3':
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{DOWNLOAD_FOLDER}/{unique_id}.%(ext)s',
            'quiet': True,
        }
    else:  # mp4
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{DOWNLOAD_FOLDER}/{unique_id}.%(ext)s',
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
async def read_root():
    return {"message": "YouTube Downloader API is running"}

@app.get("/info")
async def get_info(url: str = Query(..., description="YouTube video URL")):
    """Get information about a YouTube video"""
    return get_video_info(url)

@app.get("/download")
async def download(
    url: str = Query(..., description="YouTube video URL"),
    format: str = Query('mp4', description="Output format (mp3 or mp4)", regex="^(mp3|mp4)$")
):
    """Download YouTube video as MP3 or MP4"""
    video_info = get_video_info(url)
    filename = download_youtube_video(url, format)
    
    # Generate a clean filename for the download
    clean_title = sanitize_filename(video_info['title'])
    output_filename = f"{clean_title}.{format}"
    
    # Return the file for download
    response = FileResponse(
        filename,
        media_type='audio/mpeg' if format == 'mp3' else 'video/mp4',
        filename=output_filename
    )
    
    # Clean up after sending the file
    @response.on_close
    def cleanup():
        try:
            os.remove(filename)
        except:
            pass
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
