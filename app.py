#!/usr/bin/env python3

import os
import re
import subprocess
import time
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

# === CONFIG ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "youtube_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size

# === Helpers ===
def is_valid_youtube_url(url: str) -> bool:
    pattern = r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/.+"
    return re.match(pattern, url) is not None

def download_video(url: str, max_height: int = None) -> str:
    format_str = f"bestvideo[height<={max_height}]+bestaudio/best" if max_height else "bestvideo+bestaudio/best"
    output_template = os.path.join(DOWNLOAD_DIR, "%(title).200s.%(ext)s")
    
    cmd = [
        "yt-dlp",
        "-f", format_str,
        "-o", output_template,
        "--no-playlist",
        url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            # Find the downloaded file
            for line in result.stdout.split('\n'):
                if line.startswith('[download] Destination: '):
                    return line.split('[download] Destination: ')[1].strip()
            
            # Fallback - get most recent file
            files = sorted(
                [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))],
                key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)),
                reverse=True
            )
            if files:
                return os.path.join(DOWNLOAD_DIR, files[0])
    except Exception as e:
        print(f"Download failed: {str(e)}")
    return None

# === Routes ===
@app.route('/download', methods=['GET'])
def handle_download():
    url = request.args.get('url')
    if not url or not is_valid_youtube_url(url):
        abort(400, description="Invalid or missing YouTube URL")

    try:
        max_height = int(request.args.get('quality', 1080))
    except ValueError:
        max_height = 1080

    # Try to download the video
    filepath = download_video(url, max_height)
    if not filepath or not os.path.exists(filepath):
        abort(500, description="Failed to download video")

    # Serve the file
    filename = secure_filename(os.path.basename(filepath))
    return send_from_directory(
        DOWNLOAD_DIR,
        os.path.basename(filepath),
        as_attachment=True,
        download_name=filename
    )

@app.route('/cleanup', methods=['GET'])
def cleanup():
    try:
        now = time.time()
        deleted = 0
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > 3600:  # 1 hour
                    os.remove(filepath)
                    deleted += 1
        return jsonify({"status": "success", "deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
