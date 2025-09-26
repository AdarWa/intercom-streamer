# Use a Raspberry Pi / ARM64 base image with Go installed
FROM arm64v8/golang:1.21-bullseye

# Install dependencies needed for GoCV Raspberry Pi install
RUN apt-get update && apt-get install -y \
    build-essential cmake pkg-config git libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev libv4l-dev libxvidcore-dev \
    libx264-dev libgtk-3-dev libatlas-base-dev gfortran libtbb2 libtbb-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt

# Clone GoCV repository
RUN git clone https://github.com/hybridgroup/gocv.git

WORKDIR /opt/gocv

# Install GoCV for Raspberry Pi
RUN make install_raspi

# Set Go environment
ENV GOPATH=/go
ENV PATH=$PATH:$GOPATH/bin

# Copy your Go project
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .

# Build your GoCV project
RUN go build -o app .

# Run the app
CMD ["./app"]
