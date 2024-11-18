import depthai as dai

from ..error import CameraShutDownException
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

    def __get_sensor_queues(self, sensor_name: str, q_type_input: bool):
        get_queue = (
            self.camera_handle.getInputQueue
            if q_type_input
            else self.camera_handle.getOutputQueue
        )

        return {
            k: get_queue(v)
            for k, v in (
                self.pipeline.input_queues.get(sensor_name)
                if q_type_input
                else self.pipeline.output_queues.get(sensor_name)
            ).items()
        }

    def reload_sensors(self):
        self.sensors: dict[str, Sensor] = {}

        if self.camera_handle is None:
            return

        for [sensor_name, sensor_features] in self.all_sensors.items():
            if sensor_name in self.pipeline.cameras:
                output_queues = self.__get_sensor_queues(sensor_name, False)

                for queue in output_queues.values():
                    pass
                    # queue.setBlocking(False)
                    # queue.setMaxSize(10)

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

    def open(self, pipeline: Pipeline):
        device_info = dai.DeviceInfo(self.mxid)
        self.close()
        self.camera_handle = dai.Device(pipeline.pipeline, device_info)
        self.pipeline = pipeline
        self.reload_sensors()

        return self

    def deploy_nn(self, nn: CameraNNConfig):
        self.pipeline = NNPipeline([nn])

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

        chip_temp = self.camera_handle.getChipTemperature()
        cmx_mem_usage = self.camera_handle.getCmxMemoryUsage()
        ddr_mem_usage = self.camera_handle.getDdrMemoryUsage()

        return {
            "chip_temp": {
                "average": chip_temp.average,
                "css": chip_temp.css,
                "dss": chip_temp.dss,
                "mss": chip_temp.mss,
                "upa": chip_temp.upa,
            },
            "cmx_mem_usage": {
                "total": cmx_mem_usage.total,
                "used": cmx_mem_usage.used,
                "remaining": cmx_mem_usage.remaining,
            },
            "ddr_mem_usage": {
                "total": ddr_mem_usage.total,
                "used": ddr_mem_usage.used,
                "remaining": ddr_mem_usage.remaining,
            },
        }
