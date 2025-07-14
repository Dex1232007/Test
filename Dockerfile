FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py cookies.txt ./
RUN mkdir -p /app/youtube_downloads

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
