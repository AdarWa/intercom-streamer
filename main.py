from threading import Thread
import cv2
import os
import numpy as np
import logging
import mqtt
import time
import rtsp_stream as rtsp

client = None
MQTT_STATE_TOPIC = os.getenv("MQTT_STATE_TOPIC", "intercom-streamer/state")

logging.basicConfig(
    level=getattr(logging, os.getenv("LOGGING_LEVEL", "INFO")),
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)

main_frame_thread = None

def notify_callback(ring_state):
    logger.info(f"notify callback got {ring_state} ringstate")
    if client is None:
        logger.warning("MQTT client not ready; dropping state update")
        return
    client.publish(MQTT_STATE_TOPIC, str(ring_state).lower())

def quick_hash(img, size=16):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (size, size))
    return small

def check_score(frame, prev_hash):
    h = quick_hash(frame)
    diff = cv2.absdiff(prev_hash, h)
    score = np.sum(diff)
    return score

def hex_to_hsv_opencv(hex_color: str):
    # Convert hex to RGB
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # OpenCV expects BGR
    bgr = np.uint8([[[b, g, r]]]) # type: ignore
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0] # type: ignore
    return hsv  # [H, S, V] with H in 0–179, S/V in 0–255

def get_hsv_bounds(hex_color, tolerance=(10, 40, 40)):
    hsv = hex_to_hsv_opencv(hex_color)
    h, s, v = hsv
    tol_h, tol_s, tol_v = tolerance

    lower = np.array([max(h - tol_h, 0),
                      max(s - tol_s, 0),
                      max(v - tol_v, 0)])

    upper = np.array([min(h + tol_h, 179),
                      min(s + tol_s, 255),
                      min(v + tol_v, 255)])
    return lower, upper


class FrameProccessor:
    def __init__(self, callback, color="#2596be", tolerance=(10, 40, 40), no_ring_color_ratio=0.9):
        self.lower, self.upper = get_hsv_bounds(color, tolerance)
        self.no_ring_color_ratio = no_ring_color_ratio
        self.callback = callback
    
    def proccess_frame(self, frame):
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_frame, self.lower, self.upper)
        color_ratio = np.sum(mask > 0) / mask.size
        if color_ratio >= self.no_ring_color_ratio:
            logger.info(f"frame is {round(color_ratio*100, 2)}% colored; determined no ring")
            self.callback(False)
        else:
            logger.info(f"frame is {round(color_ratio*100, 2)}% colored; determined ring")
            self.callback(True)

class FrameThread(Thread):
    def __init__(self, camera_index, resolution=(640, 480), hash_score_threshold=50, frame_proccessor=None, reconnect_backoff=(1, 10)):
        super().__init__(daemon=True)
        if not frame_proccessor:
            raise ValueError("no frame proccessor supplied; not proceeding")
        self.frame_proccessor = frame_proccessor
        self.hash_score_threshold = hash_score_threshold
        self.camera_index = camera_index
        self.resolution = resolution
        self.cap = None
        self.frame = None
        self.prev_hash = None
        self.running = True
        self.reconnect_delay = reconnect_backoff[0]
        self.reconnect_backoff = reconnect_backoff

    def _open_camera(self):
        if self.cap is not None:
            self.cap.release()
        logger.info("opening camera index %s", self.camera_index)
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logger.warning("failed to open camera index %s", self.camera_index)
            return False
        width, height = self.resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        success, frame = cap.read()
        if not success or frame is None:
            logger.warning("camera opened but initial frame read failed; will retry")
            cap.release()
            return False

        self.cap = cap
        self.frame = frame
        self.prev_hash = quick_hash(frame)
        logger.info("camera connected successfully")
        return True

    def run(self):
        min_delay, max_delay = self.reconnect_backoff
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                if not self._open_camera():
                    logger.debug("camera not ready, sleeping for %s seconds", self.reconnect_delay)
                    time.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, max_delay)
                    continue
                self.reconnect_delay = min_delay
            assert self.cap
            success, frame = self.cap.read()
            if not success or frame is None:
                logger.warning("frame read failed; attempting to reopen camera")
                self.cap.release()
                self.cap = None
                continue

            self.frame = frame
            if self.prev_hash is None:
                self.prev_hash = quick_hash(frame)
                continue

            score = check_score(frame, self.prev_hash)
            self.prev_hash = quick_hash(frame)
            if score > self.hash_score_threshold:
                logger.info("frame changed; checking for ring status")
                try:
                    self.frame_proccessor.proccess_frame(frame)
                except Exception:
                    logger.exception("frame processing failed")

    def stop(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
            
    def get_current_frame(self):
        return self.frame

def list_cameras(max_cameras=5):
    available = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available

def force_proc_():
    if main_frame_thread is None or main_frame_thread.frame is None:
        logger.warning("no frame available to process on demand")
        return
    try:
        main_frame_thread.frame_proccessor.proccess_frame(main_frame_thread.frame)
    except Exception:
        logger.exception("manual frame processing failed")

if __name__ == "__main__":
    res = (int(os.getenv("FRAME_WIDTH", "640")), int(os.getenv("FRAME_HEIGHT", "480")))
    hash_score_threshold = int(os.getenv("HASH_SCORE_THRESHOLD", "50"))
    camera_index = int(os.getenv("CAMERA_INDEX", "-1"))
    if camera_index < 0:
        cameras = list_cameras()
        if not cameras:
            raise RuntimeError("No camera found")
        camera_index = min(cameras)
    color = os.getenv("COLOR","#2596be")
    tolerance = (int(os.getenv("TOLERANCE_H", "50")), int(os.getenv("TOLERANCE_S", "50")), int(os.getenv("TOLERANCE_V", "50")))
    no_ring_ratio = float(os.getenv("NO_RING_RATIO", "0.9"))
    frame_proc = FrameProccessor(notify_callback, color=color, tolerance=tolerance, no_ring_color_ratio=no_ring_ratio)
    logger.info("starting frame thread")
    main_frame_thread = FrameThread(
        camera_index=camera_index,
        resolution=res,
        hash_score_threshold=hash_score_threshold,
        frame_proccessor=frame_proc
    )
    main_frame_thread.start()
    
    logger.info("trying to initialize rtsp publisher")
    
    width, height = res
    fps = int(os.getenv("FPS", "30"))
    publish_uri = os.getenv("PUBLISH_URI", "rtsp://mediamtx:8554/stream")
    rtspThread = rtsp.RTSPThread(
        main_frame_thread.get_current_frame,
        width,
        height,
        fps,
        publish_uri
    )
    
    logger.info("trying to connect to MQTT broker")
    
    client = mqtt.MQTT(
        os.getenv("MQTT_ADDR", "mqtt5"),
        int(os.getenv("MQTT_PORT", "1883")),
        os.getenv("MQTT_USERNAME"),
        os.getenv("MQTT_PASSWORD"),
        int(os.getenv("MQTT_TIMEOUT", "5"))
    )
    
    try:
        rtspThread.start()
        logger.info("started rtsp publisher")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("received shutdown signal")
    finally:
        if main_frame_thread is not None:
            main_frame_thread.stop()
            main_frame_thread.join(timeout=2)
        if rtspThread is not None:
            rtspThread.stop()
            rtspThread.join(timeout=2)
        if client is not None:
            client.stop()
