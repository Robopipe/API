import tornado.escape
import depthai as dai

from dataclasses import asdict
from io import BytesIO

from ..camera.nn import CameraNNConfig
from ..camera.sensor_control import SensorControl
from .base_handler import CameraBaseHandler


class SensorsHandler(CameraBaseHandler):
    def get(self, mxid: str):
        sensors = list(self.camera_manager[mxid].all_sensors.keys())

        self.write({"sensors": sensors})
        self.finish()


class SensorConfigHandler(CameraBaseHandler):
    def get(self, mxid: str, sensor_name: str):
        camera_config = self.camera_manager[mxid].sensors[sensor_name].camera_config

        self.finish(asdict(camera_config))

    def post(self, mxid: str, sensor_name: str):
        sensor = self.camera_manager[mxid].sensors[sensor_name]
        sensor.camera_config = tornado.escape.json_decode(self.request.body)

        self.finish(asdict(sensor.camera_config))


class SensorControlHandler(CameraBaseHandler):
    def get(self, mxid: str, sensor_name: str):
        sensor_control = self.camera_manager[mxid].sensors[sensor_name].sensor_control

        self.finish(asdict(sensor_control))

    def post(self, mxid: str, sensor_name: str):
        sensor = self.camera_manager[mxid].sensors[sensor_name]
        sensor.sensor_control = SensorControl(
            **(
                asdict(sensor.sensor_control)
                | tornado.escape.json_decode(self.request.body)
            )
        )

        self.finish(asdict(sensor.sensor_control))


class SensorCaptureHandler(CameraBaseHandler):
    def get(self, mxid: str, sensor_name: str):
        format = self.get_argument("format", "jpeg")
        camera = self.camera_manager[mxid]
        image = camera.sensors[sensor_name].capture_still()
        image_bytes = BytesIO()

        try:
            image.save(image_bytes, format)
        except:
            self.set_status(400, "Unsupported image format")
            self.finish()
            return

        self.set_header("Content-Type", f"image/{format}")
        self.finish(image_bytes.getvalue())


class SensorNNHandler(CameraBaseHandler):
    def post(self, mxid: str, sensor_name: str):
        nn_blob_files = self.request.files.get("nn_blob")

        if nn_blob_files is None:
            return

        nn_blob_file = nn_blob_files[0]
        blob = dai.OpenVINO.Blob(list(nn_blob_file.body))
        nn_config = CameraNNConfig(dai.CameraBoardSocket.CAM_A, blob)
        self.camera_manager[mxid].deploy_nn(nn_config)

        self.finish({"status": "ok"})
