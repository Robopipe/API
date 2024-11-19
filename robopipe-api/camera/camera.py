import depthai as dai

import time

from ..error import CameraShutDownException
from ..log import logger
from .camera_stats import CameraStats
from .pipeline import Pipeline, NNPipeline
from .nn import CameraNNConfig
from .sensor import Sensor


class Camera:
    camera_handle: dai.Device | None = None

    def __init__(self, mxid: str, pipeline: Pipeline | None = None):
        self.mxid = mxid

        self.camera_handle = dai.Device(mxid)
        self.all_sensors = {
            sensor.socket.name: sensor
            for sensor in self.camera_handle.getConnectedCameraFeatures()
        }
        self.close()

        if pipeline is not None:
            self.open(pipeline)

    def __del__(self):
        self.close()

    def __boot_camera(self, retries: int = 5, timeout_base: float = 1):
        timeout = timeout_base
        for _ in range(retries):
            try:
                self.camera_handle = dai.Device(
                    self.pipeline.pipeline, dai.DeviceInfo(self.mxid)
                )
                return
            except:
                time.sleep(timeout)
                timeout *= 2

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
        self.sensors: dict[str, Sensor] = {}

        if self.camera_handle is None:
            return

        for [sensor_name, sensor_features] in self.all_sensors.items():
            if sensor_name in self.pipeline.cameras:
                output_queues = self.__get_sensor_queues(sensor_name, False)

                # for queue_type, queue in output_queues.items():
                #     if queue_type in [PipelineQueueType.STILL]:
                #         queue.setBlocking(False)
                #         queue.setMaxSize(1)

                self.sensors[sensor_name] = Sensor(
                    self.pipeline.cameras[sensor_name],
                    self.__get_sensor_queues(sensor_name, True),
                    output_queues,
                    lambda: self.open(self.pipeline),
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

    def deploy_nn(self, nn: CameraNNConfig):
        self.pipeline = NNPipeline([nn], self.pipeline.pipeline)

        self.open(self.pipeline)

    @property
    def info(self):
        if self.camera_handle is not None:
            return self.camera_handle.getDeviceInfo()

        devices = dai.Device.getAllConnectedDevices()

        for dev in devices:
            if dev.getMxId() == self.mxid:
                return dev

    @property
    def stats(self):
        if self.camera_handle is None:
            raise CameraShutDownException()

        return CameraStats.from_device(self.camera_handle)
