import av

import fractions
import io
import math


from .camera.camera import Camera


class VideoEncoder:
    CONTAINER_OPTIONS = {
        "movflags": "frag_keyframe+empty_moov+faststart+default_base_moof",
        "flush_packets": "1",
    }
    ENCODER_OPTIONS = {
        "tune": "zerolatency",
        "preset": "ultrafast",
        "reset_timestamps": "1",
    }

    def __init__(
        self,
        camera: Camera,
        sensor_name: str,
        container_options: dict = CONTAINER_OPTIONS,
        encoder_options: dict = ENCODER_OPTIONS,
    ):
        self.camera = camera
        self.sensor_name = sensor_name
        self.buffer = io.BytesIO()
        self.container = av.open(self.buffer, "w", "mp4", options=container_options)

        sensor = camera.sensors[sensor_name]
        sample_frame = sensor.get_video_frame()

        fps = fractions.Fraction(120)
        video_stream = self.container.add_stream("h264", fps, options=encoder_options)
        video_stream.rate = fps
        video_stream.width = sample_frame.width
        video_stream.height = sample_frame.height
        video_stream.gop_size = 1
        bit_rate = math.ceil(
            sample_frame.width
            * sample_frame.height
            * 0.5  # High Quality video
            * sensor.config.fps
        )
        video_stream.bit_rate = bit_rate
        self.video_stream = video_stream
        self.initialization_fragment = self.next()

    def __del__(self):
        self.close()

    def close(self):
        """Explicitly close resources."""
        try:
            if hasattr(self, 'container') and self.container:
                self.container.close()
        except Exception:
            pass
        try:
            if hasattr(self, 'buffer') and self.buffer:
                self.buffer.close()
        except Exception:
            pass

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        sensor = self.camera.sensors.get(self.sensor_name)
        if sensor is None:
            self.close()
            raise StopIteration()

        try:
            frame = sensor.get_video_frame()
        except Exception:
            self.close()
            raise StopIteration()

        try:
            packets = self.video_stream.encode(frame)
            self.container.mux(packets)
            buffer = self.buffer.getvalue()

            self.buffer.seek(0)
            self.buffer.truncate()

            return buffer
        except Exception:
            self.close()
            raise StopIteration()

    @property
    def init_fragment(self):
        return self.initialization_fragment
