import depthai as dai

import time

from ..error import CameraShutDownException, CameraException
from ..log import logger
from ..models.nn_config import NNConfig, NNType
from .camera_stats import CameraStats
from .device_info import DeviceInfo
from .ir import IRConfig
from .pipeline.depth_pipeline import DepthPipeline
from .pipeline.pipeline import EmptyPipeline, Pipeline, PipelineQueueType
from .pipeline.streaming_pipeline import StreamingPipeline
from .pipeline.nn_pipeline import NNPipeline
from .nn import CameraNNConfig, CameraNNMobileNetConfig, CameraNNYoloConfig
from .sensor.depth_sensor import DepthSensor
from .sensor.sensor_base import SensorBase
from .sensor.sensor import Sensor


class Camera:
    DEFAULT_POE_IP = "169.254.1.222"
    NN_CONFIG_MAP: dict[NNType, type[CameraNNConfig]] = {
        NNType.Generic: CameraNNConfig,
        NNType.YOLO: CameraNNYoloConfig,
        NNType.MobileNet: CameraNNMobileNetConfig,
    }

    def __init__(self, mxid: str, name: str, pipeline: Pipeline | None = None):
        self.mxid = mxid
        self.boot_name = name if name == Camera.DEFAULT_POE_IP else mxid
        logger.debug(f"[Camera.__init__] Creating device with boot_name={self.boot_name}")
        self.camera_handle = dai.Device(self.boot_name)
        logger.debug(f"[Camera.__init__] Device created, creating pipeline")
        self.pipeline = pipeline or EmptyPipeline(None, self.camera_handle)
        logger.debug(f"[Camera.__init__] Pipeline created: {type(self.pipeline).__name__}")
        self.__boot_camera()
        self.camera_name: str = self.camera_handle.getDeviceName()
        self.sensors: dict[str, SensorBase] = {}
        self.all_sensors = {
            sensor.socket.name: sensor
            for sensor in self.camera_handle.getConnectedCameraFeatures()
        }
        self._ir_config = IRConfig() if self.camera_name.endswith("PRO") else None

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

    def __boot_camera(self, retries: int = 5, timeout_base: float = 1):
        timeout = timeout_base
        last_exception = None
        logger.debug(f"[Camera.__boot_camera] Starting pipeline boot (retries={retries})")

        for attempt in range(retries):
            try:
                logger.debug(f"[Camera.__boot_camera] Attempt {attempt + 1}/{retries} - calling pipeline.start()")
                self.pipeline.pipeline.start()
                logger.debug(f"[Camera.__boot_camera] Pipeline started successfully")
                return
            except Exception as e:
                logger.error(f"[Camera.__boot_camera] Attempt {attempt + 1} failed: {e}")
                # self.pipeline.pipeline.stop()
                last_exception = e
                time.sleep(timeout)
                timeout *= 2

        logger.error(f"[Camera.__boot_camera] All {retries} attempts failed")
        raise CameraException(last_exception)

    def __get_sensor_queues(self, sensor_name: str, q_type_input: bool):
        # def get_queue(q_type: PipelineQueueType, q_name: str):
        #     if q_type_input:
        #         return self.camera_handle.getInputQueue(q_name)
        #     elif q_type == PipelineQueueType.STILL:
        #         return self.camera_handle.getOutputQueue(
        #             q_name, blocking=False, maxSize=1
        #         )
        #     else:
        #         return self.camera_handle.getOutputQueue(q_name)

        # return {
        #     k: get_queue(k, v)
        #     for k, v in (
        #         (
        #             self.pipeline.input_queues.get(sensor_name)
        #             if q_type_input
        #             else self.pipeline.output_queues.get(sensor_name)
        #         )
        #         or {}
        #     ).items()
        # }

        return {
            k: self.pipeline.inputs[v] if q_type_input else self.pipeline.outputs[v]
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
        existing_sensors = self.sensors
        self.sensors = {}
        restart_pipeline = lambda: self.open(self.pipeline)
        print(f"[reload_sensors] all_sensors: {list(self.all_sensors.keys())}")
        print(f"[reload_sensors] pipeline.cameras: {list(self.pipeline.cameras.keys())}")
        print(f"[reload_sensors] pipeline.output_queues: {self.pipeline.output_queues}")
        for [sensor_name, sensor_features] in self.all_sensors.items():
            if sensor_name in self.pipeline.cameras:
                input_queues = self.__get_sensor_queues(sensor_name, True)
                output_queues = self.__get_sensor_queues(sensor_name, False)
                print(f"[reload_sensors] Creating sensor {sensor_name} with output_queues: {list(output_queues.keys())}")
                sensor = Sensor(
                    sensor_features,
                    self.pipeline.cameras[sensor_name],
                    input_queues,
                    output_queues,
                    restart_pipeline,
                )

                self.sensors[sensor_name] = sensor

                if sensor_name in existing_sensors:
                    existing_sensor = existing_sensors[sensor_name]
                    sensor.control = existing_sensor.control
                    sensor.nn_config = existing_sensor.nn_config

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
            if self.pipeline is not None:
                try:
                    self.pipeline.pipeline.stop()
                except Exception:
                    pass  # Pipeline might already be stopped
                self.pipeline = None
            self.camera_handle.close()
            self.camera_handle = None
            logger.debug(f"Closed camera {self.mxid}")

    def open(self, pipeline: Pipeline | None = None):
        logger.debug(f"[Camera.open] Closing existing connection")
        self.close()
        logger.debug(f"[Camera.open] Creating new device with boot_name={self.boot_name}")
        self.camera_handle = dai.Device(self.boot_name)
        logger.debug(f"[Camera.open] Device created successfully for {self.mxid}")

        if pipeline is not None:
            logger.debug(f"[Camera.open] Running pipeline: {type(pipeline).__name__}")
            self.run_pipeline(pipeline)

        return self

    def run_pipeline(self, pipeline: Pipeline):
        if self.camera_handle is None:
            raise CameraShutDownException()

        self.pipeline = pipeline
        self.__boot_camera()
        self.reload_sensors()

    def activate_sensor(self, sensor_name: str):
        if self.camera_handle is None:
            raise CameraShutDownException()

        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Serve is in invalid state")

        # In v3, cannot modify built pipeline - must recreate with new sensor list
        # Collect currently active sensors
        active_sensors = [
            self.all_sensors[name]
            for name in self.pipeline.cameras.keys()
            if name in self.all_sensors
        ]

        # Add the new sensor
        if sensor_name in self.all_sensors:
            new_sensor = self.all_sensors[sensor_name]
            if new_sensor not in active_sensors:
                active_sensors.append(new_sensor)

        # Close and reopen with fresh pipeline
        self.close()
        self.camera_handle = dai.Device(self.boot_name)

        if sensor_name.startswith("DEPTH"):
            left, right = sensor_name.split("_")[1:]
            stereo_pair = (f"CAM_{left}", f"CAM_{right}")
            self.pipeline = DepthPipeline(stereo_pair, active_sensors, device=self.camera_handle)
        else:
            self.pipeline = StreamingPipeline(active_sensors, device=self.camera_handle)

        self.__boot_camera()
        self.reload_sensors()

    def deactivate_sensor(self, sensor_name: str):
        if self.camera_handle is None:
            raise CameraShutDownException()

        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Server is in invalid state")

        # In v3, cannot modify built pipeline - must recreate without this sensor
        # Collect currently active sensors, excluding the one to deactivate
        active_sensors = [
            self.all_sensors[name]
            for name in self.pipeline.cameras.keys()
            if name in self.all_sensors and name != sensor_name
        ]

        # Close and reopen with fresh pipeline
        self.close()
        self.camera_handle = dai.Device(self.boot_name)

        self.pipeline = StreamingPipeline(active_sensors, device=self.camera_handle)

        self.__boot_camera()
        self.reload_sensors()

    def _check_device_connected(self, context: str) -> bool:
        """Check if device is still connected and log the status."""
        try:
            if self.camera_handle is None:
                logger.warning(f"[Device Check - {context}] camera_handle is None")
                return False
            # Try to query something to see if device is alive
            connected = not self.camera_handle.isClosed()
            logger.debug(f"[Device Check - {context}] Device connected: {connected}")
            return connected
        except Exception as e:
            logger.error(f"[Device Check - {context}] Error checking device: {e}")
            return False

    def deploy_nn(self, sensor_name: str, blob: dai.OpenVINO.Blob | dai.NNArchive, config: NNConfig):
        logger.debug(f"[Camera.deploy_nn] Deploying NN to sensor={sensor_name}, type={config.type}")
        nn_config_cls = Camera.NN_CONFIG_MAP.get(config.type)

        if nn_config_cls is None:
            raise ValueError(f"Invalid NNConfig type: {config.type}")

        logger.debug(f"[Camera.deploy_nn] Creating NN config: {nn_config_cls.__name__}")
        nn = nn_config_cls(
            sensor_name,
            self.all_sensors[sensor_name],
            blob,
            config.num_inference_threads,
            **(config.nn_config.model_dump() if config.nn_config is not None else {}),
        )
        logger.debug(f"[Camera.deploy_nn] NN config created, input_shape={nn.input_shape}")

        self.sensors[sensor_name].nn_config = config

        # In v3, cannot add queues to a built pipeline - must create fresh one
        logger.debug(f"[Camera.deploy_nn] Closing existing device connection")
        self.close()
        logger.debug(f"[Camera.deploy_nn] Creating new device with boot_name={self.boot_name}")
        self.camera_handle = dai.Device(self.boot_name)
        self._check_device_connected("after device creation")

        logger.debug(f"[Camera.deploy_nn] Device created, now creating NNPipeline")

        # Create fresh NNPipeline with device (not reusing old pipeline)
        self.pipeline = NNPipeline([nn], device=self.camera_handle)
        self._check_device_connected("after NNPipeline creation")

        logger.debug(f"[Camera.deploy_nn] NNPipeline created, booting camera")

        self.__boot_camera()
        logger.debug(f"[Camera.deploy_nn] Camera booted, reloading sensors")
        self.reload_sensors()
        logger.debug(f"[Camera.deploy_nn] NN deployment complete")

    def delete_nn(self, sensor_name: str):
        if isinstance(self.pipeline, NNPipeline):
            self.sensors[sensor_name].nn_config = None
            self.pipeline.remove_nn(sensor_name)
            self.open(self.pipeline)

    @property
    def info(self) -> DeviceInfo | None:
        if self.camera_handle is not None:
            return DeviceInfo.from_device_info(
                self.camera_handle.getDeviceInfo(), self.camera_name
            )

        devices = dai.Device.getAllConnectedDevices()
        device_info = None

        for dev in devices:
            if dev.deviceId == self.mxid:
                device_info = dev
                break

        if device_info is not None:
            return DeviceInfo.from_device_info(device_info, self.camera_name)

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
