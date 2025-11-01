import gi
import cv2
import time
from gi.repository import Gst, GstRtspServer, GObject
import logging

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, frame_provider, width, height, fps, **properties):
        super(SensorFactory, self).__init__(**properties)
        self.frame_provider = frame_provider  # lambda or callable returning a frame (np.ndarray BGR)
        self.number_frames = 0
        self.fps = fps
        self.width = width
        self.height = height
        self.duration = 1 / self.fps * Gst.SECOND

        self.launch_string = (
            f'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME '
            f'caps=video/x-raw,format=BGR,width={self.width},height={self.height},framerate={self.fps}/1 '
            '! videoconvert ! video/x-raw,format=I420 '
            '! x264enc speed-preset=ultrafast tune=zerolatency '
            '! rtph264pay config-interval=1 name=pay0 pt=96'
        )

    def on_need_data(self, src, length):
        # Try to get a frame from the lambda
        frame = self.frame_provider()
        if frame is None:
            time.sleep(0.001)
            return

        frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        data = frame.tobytes()

        buf = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)
        buf.duration = self.duration
        timestamp = self.number_frames * self.duration
        buf.pts = buf.dts = int(timestamp)
        buf.offset = timestamp
        self.number_frames += 1
        retval = src.emit('push-buffer', buf)
        if retval != Gst.FlowReturn.OK:
            logging.error("Push buffer error: %s", retval)

    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)

    def do_configure(self, rtsp_media):
        self.number_frames = 0
        appsrc = rtsp_media.get_element().get_child_by_name('source')
        appsrc.connect('need-data', self.on_need_data)

class GstServer(GstRtspServer.RTSPServer):
    def __init__(self, frame_provider, width=640, height=480, fps=30, port=8554, stream_uri="/test", **properties):
        super(GstServer, self).__init__(**properties)
        self.factory = SensorFactory(frame_provider, width, height, fps)
        self.factory.set_shared(True)
        self.set_service(str(port))
        self.get_mount_points().add_factory(stream_uri, self.factory)
        self.attach(None)

def start_rtsp(frame_provider, width=640, height=480, fps=30, port=8554, stream_uri="/test"):
    GObject.threads_init()
    Gst.init(None)
    server = GstServer(frame_provider, width, height, fps, port, stream_uri)
    loop = GObject.MainLoop()
    logging.info(f"RTSP stream ready at rtsp://localhost:{port}{stream_uri}")
    loop.run()