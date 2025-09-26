import cv2
import threading
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import os

PORT = 8000

# Camera setup
cap = cv2.VideoCapture(int(os.getenv("CAMERA_INDEX", 0)))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Shared variables
latest_frame = None
last_processed_frame = None
processing_lock = threading.Lock()

def process_frame(frame):
    """Background processing function"""
    print("Processing frame...")
    # Example: convert to grayscale and save
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cv2.imwrite("processed.jpg", gray)

def frames_are_different(frame1, frame2, threshold=50):
    """Check if frames are sufficiently different"""
    diff = cv2.absdiff(frame1, frame2)
    score = np.sum(diff) / diff.size
    return score > threshold

def capture_loop():
    """Continuously capture frames and process changes"""
    global latest_frame, last_processed_frame

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        latest_frame = frame.copy()

        # Check if frame changed enough to process
        if last_processed_frame is None or frames_are_different(frame, last_processed_frame):
            if not processing_lock.locked():
                threading.Thread(target=lambda: (processing_lock.acquire(),
                                                 process_frame(frame),
                                                 processing_lock.release())).start()
            last_processed_frame = frame.copy()

        # Small sleep to reduce CPU usage
        time.sleep(0.01)

class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()

            try:
                while True:
                    if latest_frame is None:
                        time.sleep(0.01)
                        continue

                    # Encode latest frame as JPEG
                    ret, jpeg = cv2.imencode('.jpg', latest_frame)
                    if not ret:
                        continue

                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(jpeg)))
                    self.end_headers()
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b'\r\n')

                    time.sleep(0.03)  # ~30 FPS
            except BrokenPipeError:
                print("Client disconnected")
            except Exception as e:
                print("Error:", e)
        else:
            self.send_error(404)
            self.end_headers()

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), MJPEGHandler)
    print(f"Streaming at http://0.0.0.0:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    # Start capture thread
    threading.Thread(target=capture_loop, daemon=True).start()
    # Start MJPEG server
    run_server()
