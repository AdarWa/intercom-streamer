# Use Raspberry Pi compatible Python base image
FROM python:3.12-slim-bullseye

# Install dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    v4l-utils \
    pkg-config \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCV headless (no GUI, smaller image)
RUN pip install --no-cache-dir opencv-python-headless numpy flask

# Copy your Python script into the container
COPY main.py /app/main.py

WORKDIR /app

# Expose port for MJPEG streaming
EXPOSE 8000

# Run the script
CMD ["python", "main.py"]
