import depthai as dai

import time

from ..error import CameraShutDownException, CameraException
from ..log import logger
from .camera_stats import CameraStats
from .device_info import DeviceInfo
from .ir import IRConfig
from .pipeline.depth_pipeline import DEPTH_SENSOR_NAME, DepthPipeline
from .pipeline.pipeline import Pipeline
from .pipeline.streaming_pipeline import StreamingPipeline
from .pipeline.nn_pipeline import NNPipeline
from .nn import CameraNNConfig
from .sensor.depth_sensor import DepthSensor
from .sensor.sensor_base import SensorBase
from .sensor.sensor import Sensor


class Camera:
    DEFAULT_POE_IP = "169.254.1.222"

    def __init__(self, mxid: str, name: str, pipeline: Pipeline | None = None):
        self.mxid = mxid
        self.boot_name = name if name == Camera.DEFAULT_POE_IP else mxid

        self.camera_handle = dai.Device(self.boot_name)
        self.all_sensors = {
            sensor.socket.name: sensor
            for sensor in self.camera_handle.getConnectedCameraFeatures()
        }
        self._ir_config = (
            IRConfig() if len(self.camera_handle.getIrDrivers()) >= 1 else None
        )

        for stereo_pair in self.camera_handle.getAvailableStereoPairs():
            format_stereo_name = (
                lambda x, y: f"DEPTH_{x.split('_')[-1]}_{y.split('_')[-1]}"
            )
            self.all_sensors[
                format_stereo_name(stereo_pair.left.name, stereo_pair.right.name)
            ] = dai.CameraFeatures()

        self.close()

        if pipeline is not None:
            self.open(pipeline)

    def __del__(self):
        self.close()

    def __boot_camera(self, retries: int = 1, timeout_base: float = 1):
        timeout = timeout_base
        last_exception = None

        for _ in range(retries):
            try:
                self.camera_handle = dai.Device(
                    self.pipeline.pipeline, dai.DeviceInfo(self.boot_name)
                )
                return
            except Exception as e:
                last_exception = e
                time.sleep(timeout)
                timeout *= 2

        raise CameraException(last_exception)

    def __get_sensor_queues(self, sensor_name: str, q_type_input: bool):
        get_queue = (
            self.camera_handle.getInputQueue
            if q_type_input
            else self.camera_handle.getOutputQueue
        )

        return {
            k: get_queue(v)
            for k, v in (
                (
                    self.pipeline.input_queues.get(sensor_name)
                    if q_type_input
                    else self.pipeline.output_queues.get(sensor_name)
                )
                or {}
            ).items()
        }

    def reload_sensors(self):
        self.sensors: dict[str, SensorBase] = {}

        if self.camera_handle is None:
            return

        restart_pipeline = lambda: self.open(self.pipeline)

        for [sensor_name, sensor_features] in self.all_sensors.items():
            if sensor_name in self.pipeline.cameras:
                self.sensors[sensor_name] = Sensor(
                    sensor_features,
                    self.pipeline.cameras[sensor_name],
                    self.__get_sensor_queues(sensor_name, True),
                    self.__get_sensor_queues(sensor_name, False),
                    restart_pipeline,
                )

        if (
            not any(map(lambda x: x.startswith("DEPTH"), self.all_sensors.keys()))
            or not isinstance(self.pipeline, DepthPipeline)
            or self.pipeline.stereo_node is None
        ):
            return

        depth_name = self.pipeline.get_depth_name()
        self.sensors[depth_name] = DepthSensor(
            (self.pipeline.cam_left_node, self.pipeline.cam_right_node),
            self.__get_sensor_queues(depth_name, True),
            self.__get_sensor_queues(depth_name, False),
            restart_pipeline,
        )

    def close(self):
        if self.camera_handle is not None:
            self.camera_handle.close()
            self.camera_handle = None
            self.pipeline = None
            logger.debug(f"Closed camera {self.mxid}")

    def open(self, pipeline: Pipeline):
        self.close()
        self.pipeline = pipeline
        self.__boot_camera()
        self.reload_sensors()
        logger.debug(f"Opened camera {self.mxid}")

        return self

    def activate_sensor(self, sensor_name: str):
        if self.camera_handle is None:
            raise CameraShutDownException()

        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Serve is in invalid state")

        if sensor_name.startswith("DEPTH"):
            left, right = sensor_name.split("_")[1:]
            stereo_pair = (f"CAM_{left}", f"CAM_{right}")

            if isinstance(self.pipeline, DepthPipeline):
                self.pipeline.add_stereo_pair(*stereo_pair)
            else:
                self.pipeline = DepthPipeline(stereo_pair, [], self.pipeline.pipeline)
        else:
            self.pipeline.add_sensor(self.all_sensors[sensor_name])

        self.open(self.pipeline)

    def deactivate_sensor(self, sensor_name: str):
        if self.camera_handle is None:
            raise CameraShutDownException()

        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Server is in invalid state")

        self.pipeline.remove_sensor(sensor_name)
        self.open(self.pipeline)

    def deploy_nn(self, nn: CameraNNConfig):
        self.pipeline = NNPipeline([nn], self.pipeline.pipeline)

        self.open(self.pipeline)

    def delete_nn(self, sensor_name: str):
        if isinstance(self.pipeline, NNPipeline):
            self.pipeline.remove_nn(sensor_name)
            self.open(self.pipeline)

    @property
    def info(self) -> DeviceInfo | None:
        if self.camera_handle is not None:
            return DeviceInfo.from_device_info(self.camera_handle.getDeviceInfo())

        devices = dai.Device.getAllConnectedDevices()

        for dev in devices:
            if dev.getMxId() == self.mxid:
                device_info = dev
                break

        if device_info:
            return DeviceInfo.from_device_info(device_info)

    @property
    def stats(self):
        if self.camera_handle is None:
            raise CameraShutDownException()

        return CameraStats.from_device(self.camera_handle)

    @property
    def ir_config(self):
        return self._ir_config

    @ir_config.setter
    def ir_config(self, ir_config: IRConfig):
        if self._ir_config is None:
            return

        self._ir_config = ir_config

        if self.camera_handle is not None:
            self.camera_handle.setIrFloodLightIntensity(self._ir_config.flood_light)
            self.camera_handle.setIrLaserDotProjectorIntensity(
                self._ir_config.dot_projector
            )
