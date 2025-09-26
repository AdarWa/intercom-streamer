# Stage 1: Build GoCV using prebuilt static OpenCV
FROM --platform=$BUILDPLATFORM ghcr.io/hybridgroup/opencv:4.12.0-static AS gocv-build

# Install Go
ENV GO_VERSION=1.22.2
RUN wget -q https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz -O /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && rm /tmp/go.tar.gz
ENV PATH=$PATH:/usr/local/go/bin
ENV GOPATH=/go
RUN chmod +x /usr/local/go/bin/go


# Install pkg-config in case it's missing
RUN apt-get update && apt-get install -y pkg-config && rm -rf /var/lib/apt/lists/*

# Copy GoCV source
COPY . /go/src/gocv.io/x/gocv
WORKDIR /go/src/gocv.io/x/gocv

# Set CGO flags for static linking
ENV CGO_CFLAGS="-I/usr/local/include/opencv4"
ENV CGO_LDFLAGS="-L/usr/local/lib -lopencv_core -lopencv_imgproc -lopencv_imgcodecs -ltbb -ldl -lm -lpthread"

# Build gocv_version statically
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    go build -tags static -x -o /build/gocv_version ./cmd/version/

# Stage 2: Minimal runtime image
FROM debian:bullseye-slim AS final
COPY --from=gocv-build /build/gocv_version /run/gocv_version
CMD ["/run/gocv_version"]
