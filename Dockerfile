# Stage 1: Build OpenCV with TBB statically
FROM ubuntu:22.04 AS builder

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake git pkg-config \
    libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    libv4l-dev libxvidcore-dev libx264-dev \
    libgtk-3-dev libatlas-base-dev gfortran \
    wget unzip

WORKDIR /opencv_build

# Clone OpenCV
RUN git clone https://github.com/opencv/opencv.git && \
    git clone https://github.com/opencv/opencv_contrib.git

WORKDIR /opencv_build/build

# Configure OpenCV build with static TBB
RUN cmake ../opencv \
    -DOPENCV_EXTRA_MODULES_PATH=../opencv_contrib/modules \
    -DWITH_TBB=ON \
    -DBUILD_TBB=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local

# Build and install OpenCV
RUN make -j$(nproc) && make install

# Stage 2: Build GoCV project
FROM golang:latest AS go-builder

# Copy OpenCV from builder
COPY --from=builder /usr/local /usr/local

# Set environment variables for cgo
ENV CGO_CFLAGS="-I/usr/local/include/opencv4"
ENV CGO_LDFLAGS="-L/usr/local/lib -lopencv_core -lopencv_imgproc -lopencv_highgui -lopencv_videoio -lopencv_imgcodecs"

WORKDIR /app

# Copy Go module files
COPY go.mod go.sum ./
RUN go mod download

# Copy project files
COPY . .

# Build GoCV app
RUN go build -o app .

# Stage 3: Final runtime image
FROM ubuntu:22.04

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libgtk-3-0 libavcodec58 libavformat58 libswscale5 libv4l-0 libxvidcore4 libx264-163 \
    libjpeg-turbo8 libpng16-16 libtiff5 libatlas3-base libgfortran5 libstdc++6 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy app from builder
COPY --from=go-builder /app/app .

# Copy OpenCV libraries
COPY --from=builder /usr/local/lib /usr/local/lib
ENV LD_LIBRARY_PATH=/usr/local/lib

CMD ["./app"]
