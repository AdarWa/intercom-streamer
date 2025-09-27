import colorsys
from threading import Thread
import cv2
from flask import Flask, Response
import os
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def notify_callback(ring_state):
    logger.info(f"notify callback got {ring_state} ringstate")

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

def get_hsv_bounds(hex_color, tol_h=10, tol_s=40, tol_v=40):
    hsv = hex_to_hsv_opencv(hex_color)
    h, s, v = hsv

    lower = np.array([max(h - tol_h, 0),
                      max(s - tol_s, 0),
                      max(v - tol_v, 0)])

    upper = np.array([min(h + tol_h, 179),
                      min(s + tol_s, 255),
                      min(v + tol_v, 255)])
    return lower, upper


class FrameProccessor:
    def __init__(self, callback, color="#2596be", tolerance=(10,10,10), no_ring_color_ratio=0.9):
        self.upper, self.lower = get_hsv_bounds(color, *tolerance)
        self.no_ring_color_ratio = no_ring_color_ratio
        self.callback = callback
    
    def proccess_frame(self, frame):
        mask = cv2.inRange(frame, self.lower, self.upper)
        color_ratio = np.sum(mask > 0) / mask.size
        if color_ratio >= self.no_ring_color_ratio:
            logger.info(f"frame is {color_ratio*100}% colored; determined no ring")
            self.callback(False)
        else:
            logger.info(f"frame is {color_ratio*100}% colored; determined ring")
            self.callback(True)

class FrameThread(Thread):
    def __init__(self, camera_index, resolution=(640, 480), hash_score_threshold=50, frame_proccessor=None):
        super().__init__()
        if not frame_proccessor:
            raise ValueError("no frame proccessor supplied; not proceeding")
        self.frame_proccessor = frame_proccessor
        self.hash_score_threshold = hash_score_threshold
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index)
        width, height = resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        suc, frame = self.cap.read()
        if suc:
            self.prev_hash = quick_hash(frame)
        else:
            raise RuntimeError("couldn't read camera for initial hash; not proceeding")
        self.running = True

    def run(self):
        while self.running:
            success, frame = self.cap.read()
            if not success:
                continue
            self.frame = frame
            score = check_score(frame, self.prev_hash)
            self.prev_hash = quick_hash(frame)
            if score > self.hash_score_threshold:
                logger.info("frame changed; checking for ring status")
                self.frame_proccessor.proccess_frame(frame)

    def stop(self):
        self.running = False
        self.cap.release()

def list_cameras(max_cameras=5):
    available = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available

def generate_frames():
    while True:
        frame = frame_thread.frame
        if frame is None:
            break
        else:
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            # Yield frame in HTTP multipart format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

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
    tolerance = (int(os.getenv("TOLERANCE_H", "10")), int(os.getenv("TOLERANCE_S", "10")), int(os.getenv("TOLERANCE_V", "10")))
    no_ring_ratio = float(os.getenv("NO_RING_RATIO", "0.9"))
    frame_proc = FrameProccessor(notify_callback, color=color, tolerance=tolerance, no_ring_color_ratio=no_ring_ratio)
    logger.info("starting frame thread")
    frame_thread = FrameThread(camera_index=camera_index, resolution=res, hash_score_threshold=hash_score_threshold)
    frame_thread.start()
    app.run(host='0.0.0.0', port=5000)
    logger.info("started http server")
