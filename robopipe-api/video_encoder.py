import depthai as dai
import av

import fractions
import io
import math
import time


from .camera.sensor import Sensor


class VideoEncoder:
    def __init__(self, sensor: Sensor):
        self.sensor = sensor
        self.buffer = io.BytesIO()
        self.container = av.open(
            self.buffer,
            "w",
            "mp4",
            options={
                "movflags": "frag_keyframe+empty_moov+faststart+default_base_moof",
                "flush_packets": "1",
            },
        )

        sample_frame = sensor.get_video_frame()

        video_stream = self.container.add_stream(
            "h264",
            fractions.Fraction(self.sensor.camera_config.fps),
            options={
                "tune": "zerolatency",
                "preset": "ultrafast",
                "reset_timestamps": "1",
            },
        )
        video_stream.width = sample_frame.width
        video_stream.height = sample_frame.height
        video_stream.gop_size = 1
        bit_rate = math.ceil(
            sample_frame.width
            * sample_frame.height
            * 0.2  # High Quality video
            * self.sensor.camera_config.fps
        )
        video_stream.bit_rate = bit_rate
        self.video_stream = video_stream
        self.initialization_fragment = self.next()

    def __del__(self):
        self.container.close()

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        try:
            frame = self.sensor.get_video_frame()
        except:
            raise StopIteration()

        packets = self.video_stream.encode(frame)
        self.container.mux(packets)
        buffer = self.buffer.getvalue()

        self.buffer.seek(0)
        self.buffer.truncate()

        return buffer

    @property
    def init_fragment(self):
        return self.initialization_fragment
