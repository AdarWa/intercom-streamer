# Start from the GoCV image (has Go + OpenCV preinstalled)
FROM gocv/opencv:latest

# Set working directory
WORKDIR /app

# Install TBB (needed for OpenCV build in the base image)
RUN apt-get update && apt-get install -y libtbb-dev && rm -rf /var/lib/apt/lists/*

# Copy go.mod and go.sum first (to leverage caching)
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy the rest of the source code
COPY . .

# Build the project
RUN go build -o app .

# Run by default
CMD ["./app"]
