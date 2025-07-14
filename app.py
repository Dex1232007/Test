#!/usr/bin/env python3

import os
import re
import sys
import subprocess
import time
from time import sleep
from typing import Optional
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# === CONFIG ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "youtube_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

DEBUG_MODE = "--debug" in sys.argv
RETRY_COUNT = 3
RETRY_DELAY = 3  # seconds

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# === Logging ===
def log_debug(msg: str) -> None:
    if DEBUG_MODE:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")

# === Response Helpers ===
def success_response(data=None, message="Success"):
    return jsonify({
        "status": "success",
        "message": message,
        "data": data
    })

def error_response(message="Error", status_code=400):
    return jsonify({
        "status": "error",
        "message": message
    }), status_code

# === URL Validation ===
def is_valid_youtube_url(url: str) -> bool:
    # Supports youtube.com, youtu.be, and m.youtube.com
    pattern = r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/.+"
    return re.match(pattern, url) is not None

# === Fetch YouTube Stream URL with retries ===
def fetch_youtube_stream(url: str) -> Optional[str]:
    cmd = [
        "yt-dlp",
        "-f", "bestvideo+bestaudio/best",
        "--get-url",
        "--no-playlist",
        url
    ]
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            log_debug(f"Extracting direct stream URL... (Attempt {attempt})")
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30).decode().strip()
            log_debug(f"Stream URL extracted: {output}")
            return output
        except subprocess.CalledProcessError as e:
            log_debug(f"Extraction failed (Attempt {attempt}): {e}")
            log_debug(f"Error output: {e.output.decode() if hasattr(e, 'output') else str(e)}")
        except subprocess.TimeoutExpired:
            log_debug(f"Extraction timed out (Attempt {attempt})")
        sleep(RETRY_DELAY)
    return None

# === Download Video ===
def download_youtube_video(url: str, max_height: Optional[int] = None) -> Optional[str]:
    format_str = "bestvideo+bestaudio/best"
    if max_height:
        format_str = f"bestvideo[height<={max_height}]+bestaudio/best"

    output_template = os.path.join(DOWNLOAD_DIR, "%(title).200s.%(ext)s")
    
    cmd = [
        "yt-dlp",
        "-f", format_str,
        "-o", output_template,
        "--no-playlist",
        url
    ]

    try:
        log_debug(f"Downloading video with format '{format_str}'...")
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if process.returncode == 0:
            # Find the downloaded file
            output = process.stdout
            filename = None
            for line in output.split('\n'):
                if line.startswith('[download] Destination: '):
                    filename = line.split('[download] Destination: ')[1].strip()
                    break
            
            if filename and os.path.exists(filename):
                return filename
            else:
                # Try to find the most recent file in download directory
                files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
                if files:
                    files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)), reverse=True)
                    return os.path.join(DOWNLOAD_DIR, files[0])
        else:
            log_debug(f"Download failed with exit code {process.returncode}.")
            log_debug(f"Error output: {process.stderr}")
    except subprocess.TimeoutExpired:
        log_debug("Download timed out after 10 minutes.")
    except Exception as e:
        log_debug(f"Download exception: {e}")
    
    return None

# === API Endpoints ===
@app.route('/api/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return error_response("URL parameter is required")
    
    if not is_valid_youtube_url(url):
        return error_response("Invalid YouTube URL")
    
    stream_url = fetch_youtube_stream(url)
    if stream_url:
        return success_response({
            "stream_url": stream_url,
            "status": "available"
        })
    else:
        return error_response("Could not extract stream URL", 404)

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json()
    if not data:
        return error_response("Invalid JSON payload")
    
    url = data.get('url')
    if not url:
        return error_response("URL is required")
    
    if not is_valid_youtube_url(url):
        return error_response("Invalid YouTube URL")
    
    max_height = data.get('max_height')
    try:
        max_height = int(max_height) if max_height else None
    except ValueError:
        return error_response("max_height must be an integer")
    
    filename = download_youtube_video(url, max_height)
    if filename:
        return success_response({
            "filename": os.path.basename(filename),
            "download_url": f"/api/files/{os.path.basename(filename)}"
        })
    else:
        return error_response("Failed to download video", 500)

@app.route('/api/files/<filename>', methods=['GET'])
def serve_file(filename):
    # Securely serve downloaded files
    safe_filename = secure_filename(filename)
    if not os.path.exists(os.path.join(DOWNLOAD_DIR, safe_filename)):
        return error_response("File not found", 404)
    
    return send_from_directory(DOWNLOAD_DIR, safe_filename, as_attachment=True)

@app.route('/api/cleanup', methods=['POST'])
def cleanup_files():
    # Delete files older than 1 hour to save space
    try:
        now = time.time()
        deleted = 0
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > 3600:  # 1 hour
                    os.remove(file_path)
                    deleted += 1
        
        return success_response(message=f"Deleted {deleted} old files")
    except Exception as e:
        return error_response(f"Cleanup failed: {str(e)}", 500)

@app.route('/health', methods=['GET'])
def health_check():
    return success_response(message="Service is running")

# === Startup ===
if __name__ == "__main__":
    # Auto-install required packages
    def auto_install(pkg: str) -> None:
        try:
            __import__(pkg)
        except ImportError:
            print(f"⚠️ Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

    required_packages = ['flask', 'werkzeug', 'pyperclip']
    for pkg in required_packages:
        auto_install(pkg)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG_MODE)
