import cv2
from flask import Flask, Response
import os

app = Flask(__name__)

def list_cameras(max_cameras=5):
    available = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available

cap = cv2.VideoCapture(min(list_cameras()))

cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(os.getenv("FRAME_WIDTH", "640")))
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(os.getenv("FRAME_HEIGHT", "480")))

def generate_frames():
    while True:
        success, frame = cap.read()
        if not success:
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
    app.run(host='0.0.0.0', port=5000)
