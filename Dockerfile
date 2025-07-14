FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Create download directory
RUN mkdir -p /app/youtube_downloads

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
