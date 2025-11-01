FROM python:3.12

WORKDIR /app

# Install system dependencies for PyGObject and GStreamer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libcairo2-dev \
    pkg-config \
    libgirepository-2.0-dev \
    gobject-introspection \
    libglib2.0-dev \
    libffi-dev \
    meson \
    ninja-build \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    v4l-utils \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-x \
    gstreamer1.0-gl \
    gstreamer1.0-alsa \
    libgstreamer1.0-0 \
    libgstrtspserver-1.0-dev \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-rtsp-server-1.0 \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set PKG_CONFIG_PATH for girepository
ENV PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig

# Install uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies
RUN uv export > requirements.txt && \
    uv pip install --system --no-cache-dir -r requirements.txt && \
    uv pip install --system --no-cache-dir pycairo PyGObject

# Copy app code
COPY *.py /app

# Expose RTSP port
EXPOSE 8554

CMD ["python", "main.py"]
