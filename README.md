# Intercom Streamer

Intercom Streamer captures frames from a camera, detects whether the intercom has an active picture, publishes the state over MQTT, and exposes a MJPEG feed over HTTP. The project is intended to run on lightweight hardware (e.g., a Raspberry Pi) and integrates with home automation platforms that can consume MQTT events.

## Features
- Publishes `ring` / `no ring` events to a configurable MQTT topic.
- Streams the latest camera frame over HTTP for remote monitoring.
- Color-based detection that can be tuned via environment variables.
- Optional Docker/Docker Compose setup for containerized deployments.

## Requirements
- Python 3.12+
- A V4L2-compatible camera (USB or CSI).
- An accessible MQTT broker.
- OpenCV, Flask, and Paho MQTT Python packages (installed automatically when using `uv` or `pip`).

## Getting Started

### Local development
1. Install dependencies (choose one):
   - With [uv](https://github.com/astral-sh/uv): `uv sync`
   - With pip: `python -m pip install -r <(printf "flask\nopencv-python-headless\npaho-mqtt\n")`
2. Ensure the camera is connected and accessible (e.g., `/dev/video0`).
3. Export any desired environment variables (see table below).
4. Start the app: `python main.py`
5. Open a browser to `http://<host>:5000/` to view the MJPEG stream.

### Docker Compose
1. Build and start the stack: `docker compose up --build`
2. Adjust the `ports` mapping in `docker-compose.yml` if you want external port `5000` (the Flask default) instead of `8000`.
3. Pass environment variables under the `environment` section to override defaults.

## HTTP Endpoints
- `/` — MJPEG stream that serves the latest camera frames.
- `/force_proc` — Forces the detection pipeline to re-evaluate the current frame and publish the result.

## MQTT
The app connects to the configured broker on startup and publishes state updates to `MQTT_STATE_TOPIC`. Messages are simple lowercase strings: `"true"` when a ring is detected, `"false"` when the scene returns to normal.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `LOGGING_LEVEL` | `INFO` | Python logging level (e.g., `DEBUG`, `INFO`). |
| `MQTT_STATE_TOPIC` | `intercom-streamer/state` | MQTT topic used to publish ring state updates. |
| `MQTT_ADDR` | `mqtt5` | Hostname or IP address of the MQTT broker. |
| `MQTT_PORT` | `1883` | TCP port for MQTT connections. |
| `MQTT_USERNAME` | _(unset)_ | Optional MQTT username. |
| `MQTT_PASSWORD` | _(unset)_ | Optional MQTT password. |
| `MQTT_TIMEOUT` | `5` | Seconds to wait while establishing the MQTT connection before giving up. |
| `FRAME_WIDTH` | `640` | Capture resolution width in pixels. |
| `FRAME_HEIGHT` | `480` | Capture resolution height in pixels. |
| `CAMERA_INDEX` | `-1` | Index passed to OpenCV. When negative, the app auto-selects the first available camera. |
| `HASH_SCORE_THRESHOLD` | `50` | Minimum difference score between consecutive frames required to trigger detection. Increase to make the app less sensitive to minor changes. |
| `COLOR` | `#2596be` | Hex color representing the indicator to track. |
| `TOLERANCE_H` | `50` | Hue tolerance applied when building the HSV mask. |
| `TOLERANCE_S` | `50` | Saturation tolerance applied when building the HSV mask. |
| `TOLERANCE_V` | `50` | Value/brightness tolerance applied when building the HSV mask. |
| `NO_RING_RATIO` | `0.9` | Minimum ratio of matching pixels to conclude “no ring”. Lower to allow partial matches to count as a ring. |

## Troubleshooting
- Verify the container (or host) user has permission to access `/dev/video*` devices.
- Adjust `TOLERANCE_*`, `COLOR`, or `NO_RING_RATIO` if the detector produces false positives/negatives.
- Set `LOGGING_LEVEL=DEBUG` to surface detailed diagnostics for the detection pipeline and MQTT traffic.

