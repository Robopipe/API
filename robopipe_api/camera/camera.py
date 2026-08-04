import depthai as dai

import time
from pathlib import Path

from ..error import CameraShutDownException, CameraException
from ..log import logger
from ..models.nn_config import NNConfig, NNType
from ..models.still_config import StillConfig
from .camera_stats import CameraStats
from .constants import DEPTH_NAME
from .device_info import DeviceInfo
from .ir import IRConfig
from .pipeline.depth_pipeline import DepthPipeline
from .pipeline.pipeline import EmptyPipeline, Pipeline, PipelineQueueType
from .pipeline.streaming_pipeline import StreamingPipeline
from .pipeline.nn_pipeline import NNPipeline
from .nn import CameraNNConfig
from .sensor.depth_sensor import DepthSensor
from .sensor.sensor_base import SensorBase
from .sensor.sensor import Sensor


class Camera:
    DEFAULT_POE_IP = "169.254.1.222"
    NN_CONFIG_MAP: dict[NNType, type[CameraNNConfig]] = {
        NNType.Generic: CameraNNConfig,
        # NNType.YOLO: CameraNNYoloConfig,
        # NNType.MobileNet: CameraNNMobileNetConfig,
    }
    # Delay between Device close and the next Device open. Gives the on-device
    # kernel time to reap the previous depthai-device firmware's msm_cvp /
    # cam_sync / synx resources before the new firmware boot; without it,
    # rapid close/open cycles occasionally SIGABRT the firmware (RVC4 CVP
    # debugfs collision).
    DEVICE_REOPEN_SETTLE_MS = 500

    def __init__(self, mxid: str, name: str, pipeline: Pipeline | None = None):
        # Pre-set attributes that close()/__del__ touch so a failure in
        # dai.Device(...) below doesn't cause AttributeError during GC,
        # which masks the real startup error in "Application startup failed"
        # logs.
        self.camera_handle = None
        self.pipeline = None

        self.mxid = mxid
        self.boot_name = name if name == Camera.DEFAULT_POE_IP else mxid
        self.camera_handle = dai.Device(self.boot_name)
        self.pipeline = pipeline
        self.camera_name: str = self.camera_handle.getDeviceName()
        self.sensors: dict[str, SensorBase] = {}
        self.all_sensors = {
            sensor.socket.name: sensor
            for sensor in self.camera_handle.getConnectedCameraFeatures()
        }
        self._ir_config = IRConfig() if self.camera_name.endswith("PRO") else None
        self._replay_video_paths: dict[str, str] = {}

        for stereo in self.camera_handle.getAvailableStereoPairs():
            sensor_name = lambda s: s.split("_")[-1]
            stereo_name = lambda x, y: f"{DEPTH_NAME}_{sensor_name(x)}_{sensor_name(y)}"
            self.all_sensors[stereo_name(stereo.left.name, stereo.right.name)] = (
                dai.CameraFeatures()
            )

        self.close()

    def __del__(self):
        self.close()

    def __boot_camera(self, retries: int = 5, timeout_base: float = 1):
        timeout = timeout_base
        last_exception = None
        for attempt in range(retries):
            try:
                self.pipeline.pipeline.start()
                return
            except Exception as e:
                last_exception = e
                time.sleep(timeout)
                timeout *= 2

        raise CameraException(last_exception)

    def __get_sensor_queues(self, sensor_name: str, q_type_input: bool):
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
        for [sensor_name, sensor_features] in self.all_sensors.items():
            if sensor_name in self.pipeline.cameras:
                input_queues = self.__get_sensor_queues(sensor_name, True)
                output_queues = self.__get_sensor_queues(sensor_name, False)
                sensor = Sensor(
                    sensor_features,
                    self.pipeline.cameras[sensor_name],
                    input_queues,
                    output_queues,
                    restart_pipeline,
                )

                self.sensors[sensor_name] = sensor

                # Propagate SAHI state from pipeline to sensor
                if (
                    isinstance(self.pipeline, NNPipeline)
                    and sensor_name in self.pipeline.sahi_tile_queue
                ):
                    sensor._sahi_tile_queue = self.pipeline.sahi_tile_queue[sensor_name]
                    sensor._sahi_manip_cfg = self.pipeline.sahi_manip_cfg[sensor_name]
                    sensor._sahi_tiles = self.pipeline.sahi_tiles[sensor_name]
                    sensor._sahi_config = self.pipeline.sahi_configs[sensor_name]
                    sensor._sahi_model_input_size = (
                        self.pipeline.sahi_model_input_sizes[sensor_name]
                    )
                    sensor._sahi_tile_cache = [
                        [] for _ in self.pipeline.sahi_tiles[sensor_name]
                    ]

                # Populate still config from pipeline (covers both user overrides and
                # auto-derived defaults stored during add_sensor).
                if isinstance(self.pipeline, StreamingPipeline):
                    sensor.config = self.pipeline._still_configs.get(sensor_name)

                if sensor_name in existing_sensors:
                    existing_sensor = existing_sensors[sensor_name]
                    sensor.control = existing_sensor.control
                    sensor.nn_config = existing_sensor.nn_config

        if (
            not any(map(lambda x: x.startswith(DEPTH_NAME), self.all_sensors.keys()))
            or not isinstance(self.pipeline, DepthPipeline)
            or self.pipeline.stereo is None
        ):
            return

        depth_name = self.pipeline.get_depth_name()
        left_features = self.pipeline.stereo_pair[0]
        self.sensors[depth_name] = DepthSensor(
            left_features,
            (self.pipeline.cam_left, self.pipeline.cam_right),
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

    def open(self, pipeline: Pipeline | None = None):
        if self.camera_handle is not None:
            raise CameraException("Camera is already open")
        if self.DEVICE_REOPEN_SETTLE_MS > 0:
            time.sleep(self.DEVICE_REOPEN_SETTLE_MS / 1000)
        self.camera_handle = dai.Device(self.boot_name)

        if pipeline is not None or self.pipeline is not None:
            pipeline = pipeline or self.pipeline
            pipeline = type(pipeline)(device=self.camera_handle, pipeline=pipeline)
            self.pipeline = pipeline
            self.__boot_camera()
            self.reload_sensors()

        return self

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def activate_sensor(self, sensor_name: str):
        self.__check_device_active()
        if sensor_name not in self.all_sensors:
            raise ValueError(f"Sensor {sensor_name} not found on camera {self.mxid}")
        elif sensor_name in self.sensors:
            return  # Sensor already active
        elif not isinstance(self.pipeline, DepthPipeline):
            raise RuntimeError("Server is in invalid state")

        pipeline = self.pipeline
        self.close()

        if sensor_name.startswith(DEPTH_NAME):
            pipeline.add_stereo_pair_config(
                self.all_sensors[f"CAM_{sensor_name.split('_')[1]}"],
                self.all_sensors[f"CAM_{sensor_name.split('_')[2]}"],
            )
        else:
            sensor = self.all_sensors[sensor_name]
            pipeline.add_sensor_config(sensor)

        self.open(pipeline)

    def deactivate_sensor(self, sensor_name: str):
        self.__check_device_active()
        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Server is in invalid state")
        elif sensor_name not in self.pipeline.cameras:
            return  # Sensor already inactive

        pipeline = self.pipeline
        self.close()
        pipeline.remove_sensor(sensor_name)
        self.open(pipeline)

    def batch_update_sensors(
        self,
        activate: list[str],
        deactivate: list[str],
    ) -> None:
        self.__check_device_active()

        if not isinstance(self.pipeline, DepthPipeline):
            raise RuntimeError("Server is in invalid state")

        # Validate before any mutation
        overlap = set(activate) & set(deactivate)
        if overlap:
            raise ValueError(
                f"Sensors cannot be both activated and deactivated: {overlap}"
            )

        for sensor_name in activate + deactivate:
            if sensor_name not in self.all_sensors:
                raise ValueError(
                    f"Sensor {sensor_name} not found on camera {self.mxid}"
                )

        # Filter no-ops
        to_activate = [s for s in activate if s not in self.sensors]
        to_deactivate = [
            s
            for s in deactivate
            if s in self.pipeline.cameras or s == self.pipeline.get_depth_name()
        ]

        if not to_activate and not to_deactivate:
            return

        # Single close/open cycle
        pipeline = self.pipeline
        self.close()

        for sensor_name in to_deactivate:
            pipeline.remove_sensor(sensor_name)

        for sensor_name in to_activate:
            if sensor_name.startswith(DEPTH_NAME):
                pipeline.add_stereo_pair_config(
                    self.all_sensors[f"CAM_{sensor_name.split('_')[1]}"],
                    self.all_sensors[f"CAM_{sensor_name.split('_')[2]}"],
                )
            else:
                pipeline.add_sensor_config(self.all_sensors[sensor_name])

        self.open(pipeline)

    def add_replay_video(self, sensor_name: str, video_path: str):
        self.__check_device_active()
        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Server is in invalid state")
        elif sensor_name not in self.all_sensors:
            raise ValueError(f"Sensor {sensor_name} not found on camera {self.mxid}")
        elif sensor_name not in self.sensors:
            raise ValueError(f"Sensor {sensor_name} is not active")

        old_path = self._replay_video_paths.get(sensor_name)

        pipeline = self.pipeline
        self.close()
        pipeline.add_replay_video(sensor_name, video_path)
        self.open(pipeline)

        self._replay_video_paths[sensor_name] = video_path
        if old_path and old_path != video_path:
            Path(old_path).unlink(missing_ok=True)

    def get_replay_video(self, sensor_name: str) -> str | None:
        if sensor_name not in self.all_sensors:
            raise ValueError(f"Sensor {sensor_name} not found on camera {self.mxid}")
        return self._replay_video_paths.get(sensor_name)

    def remove_replay_video(self, sensor_name: str):
        self.__check_device_active()
        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Server is in invalid state")
        elif sensor_name not in self.all_sensors:
            raise ValueError(f"Sensor {sensor_name} not found on camera {self.mxid}")

        video_path = self._replay_video_paths.pop(sensor_name, None)
        if video_path is None:
            return

        pipeline = self.pipeline
        self.close()
        pipeline.remove_replay_video(sensor_name)
        self.open(pipeline)

        Path(video_path).unlink(missing_ok=True)

    def cleanup_replay_videos(self):
        for video_path in self._replay_video_paths.values():
            Path(video_path).unlink(missing_ok=True)
        self._replay_video_paths.clear()

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

    def deploy_nn(
        self,
        sensor_name: str,
        blob: dai.OpenVINO.Blob | dai.NNArchive,
        config: NNConfig,
    ):
        if not isinstance(self.pipeline, NNPipeline):
            raise RuntimeError("Server is in invalid state")

        nn_config_cls = Camera.NN_CONFIG_MAP.get(config.type)

        if nn_config_cls is None:
            raise ValueError(f"Invalid NNConfig type: {config.type}")

        nn = nn_config_cls(
            sensor_name,
            self.all_sensors[sensor_name],
            blob,
            config.num_inference_threads,
            **(config.nn_config.model_dump() if config.nn_config is not None else {}),
        )

        pipeline = self.pipeline
        self.close()
        pipeline.add_nn_config(nn)
        self.open(pipeline)

    def delete_nn(self, sensor_name: str):
        if not isinstance(self.pipeline, NNPipeline):
            return

        # Clear nn_config on the current sensor BEFORE the pipeline restart.
        # reload_sensors() propagates the old sensor's nn_config to the new
        # one on open(), so without this GET /nn keeps returning the deployed
        # config after delete — client shows a stale "NN" badge.
        existing = self.sensors.get(sensor_name)
        if existing is not None:
            existing.nn_config = None

        pipeline = self.pipeline
        self.close()
        pipeline.remove_nn(sensor_name)
        pipeline.add_sensor_config(self.all_sensors[sensor_name])
        self.open(pipeline)

    def set_still_config(self, stream_name: str, config: StillConfig) -> StillConfig:
        self.__check_device_active()
        if not isinstance(self.pipeline, StreamingPipeline):
            raise RuntimeError("Server is in invalid state")

        sensor_features = self.all_sensors.get(stream_name)
        available = StreamingPipeline.available_configs(sensor_features)
        match = next(
            (
                o
                for o in available
                if o.width == config.width
                and o.height == config.height
                and o.min_fps <= config.fps <= o.max_fps
            ),
            None,
        )
        if match is None:
            raise ValueError(
                f"Config ({config.width}x{config.height} @ {config.fps} fps) "
                "is not available for this sensor"
            )

        pipeline = self.pipeline
        previous_config = pipeline._still_configs.get(stream_name)

        pipeline._still_configs[stream_name] = config
        self.close()
        try:
            self.open(pipeline)
            return config
        except Exception as primary_error:
            self.close()
            if previous_config is not None:
                pipeline._still_configs[stream_name] = previous_config
            else:
                pipeline._still_configs.pop(stream_name, None)
            try:
                self.open(pipeline)
            except Exception as rollback_error:
                raise CameraException(
                    "Pipeline restart failed and rollback also failed"
                ) from rollback_error
            raise primary_error

    def __check_device_active(self):
        if self.camera_handle is None:
            raise CameraShutDownException()

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
