from threading import Event, Thread
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

from gi.repository import Gst
import logging

Gst.init(None)

class RTSPThread(Thread):
    def __init__(self, frame_provider, width=640, height=480, fps=30, publish_uri="rtsp://127.0.0.1:8554/stream"):
        super().__init__(daemon=True)
        self.pipeline_str = f"""
            appsrc name=src is-live=true block=true format=time !
            video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 !
            videoconvert !
            x264enc tune=zerolatency bitrate=2048 speed-preset=ultrafast !
            h264parse !
            rtspclientsink location={publish_uri} protocols=tcp
        """
        self.frame_provider = frame_provider
        self.pipeline = Gst.parse_launch(self.pipeline_str)
        self.appsrc = self.pipeline.get_by_name("src")
        self.pipeline.set_state(Gst.State.PLAYING)
        self.pts = 0
        self.duration = Gst.util_uint64_scale(1, Gst.SECOND, fps)
        self.stop_event = Event()
        self.stop_event.clear()
        self.running = True
    
    def run(self):
        while self.running and not self.stop_event.is_set():
            try:
                frame = self.frame_provider()

                buf = Gst.Buffer.new_allocate(None, frame.nbytes, None)
                buf.fill(0, frame.tobytes())
                buf.pts = buf.dts = self.pts
                buf.duration = self.duration
                self.pts += self.duration

                # Push frame
                ret = self.appsrc.emit("push-buffer", buf)
                if ret != Gst.FlowReturn.OK:
                    logging.warning(f"Push buffer returned {ret}")
            except Exception as e:
                logging.error(e)
        self.appsrc.emit("end-of-stream")
        self.pipeline.set_state(Gst.State.NULL)
    
    def stop(self):
        self.stop_event.set()
        self.running = False
