import gi
import cv2
from gi.repository import Gst, GstRtspServer, GLib
import logging

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

Gst.init(None)

class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, frame_provider, width, height, fps, **properties):
        super().__init__(**properties)
        self.frame_provider = frame_provider
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = Gst.SECOND // fps
        self.number_frames = 0

        self.launch_string = (
            f'appsrc name=source is-live=true block=false format=GST_FORMAT_TIME '
            f'caps=video/x-raw,format=BGR,width={self.width},height={self.height},framerate={self.fps}/1 '
            '! videoconvert ! video/x-raw,format=I420 '
            '! x264enc speed-preset=ultrafast tune=zerolatency '
            '! rtph264pay config-interval=1 name=pay0 pt=96'
        )

    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)

    def do_configure(self, rtsp_media):
        appsrc = rtsp_media.get_element().get_child_by_name('source')
        appsrc.connect('need-data', self.push_frame)
        appsrc.set_property('max-bytes', 0)

        # Force RTP/UDP transport instead of TCP
        rtsp_media.get_element().set_property("protocols", GstRtspServer.RTSPLowerTrans.UDP)

    def push_frame(self, src, length):
        frame = self.frame_provider()
        if frame is None:
            return

        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))

        yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
        data = yuv.tobytes()

        buf = Gst.Buffer.new_wrapped(data)
        buf.pts = buf.dts = self.number_frames * self.duration
        buf.duration = self.duration
        self.number_frames += 1

        ret = src.emit('push-buffer', buf)
        if ret != Gst.FlowReturn.OK:
            logging.warning("Push buffer returned %s", ret)

class GstServer(GstRtspServer.RTSPServer):
    def __init__(self, frame_provider, width=640, height=480, fps=30, port=8554, stream_uri="/test"):
        super().__init__()
        self.factory = SensorFactory(frame_provider, width, height, fps)
        self.factory.set_shared(True)
        self.get_mount_points().add_factory(stream_uri, self.factory)
        self.set_service(str(port))
        self.attach(None)

def start_rtsp(frame_provider, width=640, height=480, fps=30, port=8554, stream_uri="/test"):
    server = GstServer(frame_provider, width, height, fps, port, stream_uri)
    logging.info(f"RTSP UDP stream ready at rtsp://localhost:{port}{stream_uri}")
    GLib.MainLoop().run()
