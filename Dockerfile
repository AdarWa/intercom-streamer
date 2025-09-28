# Use Raspberry Pi compatible Python base image
FROM python:3.12-slim


WORKDIR /app


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

# Install curl so we can get uv
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Add uv to PATH (uv installs in ~/.local/bin)
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency file(s) first for caching
COPY pyproject.toml uv.lock* ./

# Install dependencies (using uv)
RUN uv export > requirements.txt \
    && uv pip install --system --no-cache-dir -r requirements.txt

COPY *.py /app

# Expose port for MJPEG streaming
EXPOSE 8000

# Run the script
CMD ["python", "main.py"]
