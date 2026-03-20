# 1. Base Image
FROM python:3.10-slim

# 2. System Dependencies (FFmpeg for Render)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libmagic1 \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Work Directory
WORKDIR /app

# 4. Copy Files
COPY . .

# 5. Install Dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Run Command
CMD ["python", "main.py"]
