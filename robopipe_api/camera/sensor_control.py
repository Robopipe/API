import depthai as dai
from pydantic import BaseModel, Field

from dataclasses import dataclass
from enum import Enum
import math
from typing import Annotated


class AutoFocusMode(Enum):
    OFF = dai.CameraControl.AutoFocusMode.OFF.name
    AUTO = dai.CameraControl.AutoFocusMode.AUTO.name
    MACRO = dai.CameraControl.AutoFocusMode.MACRO.name
    CONTINUOUS_VIDEO = dai.CameraControl.AutoFocusMode.CONTINUOUS_VIDEO.name
    CONTINUOUS_PICTURE = dai.CameraControl.AutoFocusMode.CONTINUOUS_PICTURE.name
    EDOF = dai.CameraControl.AutoFocusMode.EDOF.name

    @classmethod
    def from_dai_af_mode(cls, af_mode: dai.CameraControl.AutoFocusMode):
        return cls(af_mode.name)

    def to_dai_af_mode(self) -> dai.CameraControl.AutoFocusMode:
        return dai.CameraControl.AutoFocusMode.__members__[self.name]


class SensorControlAF(BaseModel):
    auto_focus_mode: AutoFocusMode
    auto_focus_trigger: bool = False
    auto_focus_region: tuple[int, int, int, int] | None = None


class SensorControlMF(BaseModel):
    manual_focus: Annotated[int, Field(strict=True, ge=0, le=255)]


class AutoWhiteBalanceMode(Enum):
    AUTO = dai.RawCameraControl.AutoWhiteBalanceMode.AUTO.name
    CLOUDY_DAYLIGHT = dai.RawCameraControl.AutoWhiteBalanceMode.CLOUDY_DAYLIGHT.name
    DAYLIGHT = dai.RawCameraControl.AutoWhiteBalanceMode.DAYLIGHT.name
    FLUORESCENT = dai.RawCameraControl.AutoWhiteBalanceMode.FLUORESCENT.name
    INCANDESCENT = dai.RawCameraControl.AutoWhiteBalanceMode.INCANDESCENT.name
    OFF = dai.RawCameraControl.AutoWhiteBalanceMode.OFF.name
    SHADE = dai.RawCameraControl.AutoWhiteBalanceMode.SHADE.name
    TWILIGHT = dai.RawCameraControl.AutoWhiteBalanceMode.TWILIGHT.name
    WARM_FLUORESCENT = dai.RawCameraControl.AutoWhiteBalanceMode.WARM_FLUORESCENT.name


class SensorControl(BaseModel):
    exposure_time: Annotated[
        int,
        Field(
            description="Exposure time in microseconds. Ignored if auto_exposure_enable is set to true.",
            ge=1,
            le=33000,
        ),
    ]
    sensitivity_iso: Annotated[int, Field(strict=True, ge=100, le=5000)]
    auto_exposure_enable: bool
    auto_exposure_compensation: Annotated[int, Field(strict=True, ge=-9, le=9)] = 0
    auto_exposure_limit: Annotated[
        int,
        Field(
            description="Maximum exposure time limit for auto-exposure in microseconds"
        ),
    ]
    auto_exposure_lock: bool
    contrast: Annotated[int, Field(strict=True, ge=-10, le=10)] = 0
    brightness: Annotated[int, Field(strict=True, ge=-10, le=10)] = 0
    saturation: Annotated[int, Field(strict=True, ge=-10, le=10)] = 0
    chroma_denoise: Annotated[int, Field(strict=True, ge=0, le=4)] = 1
    luma_denoise: Annotated[int, Field(strict=True, ge=0, le=4)] = 1
    auto_whitebalance_lock: bool
    auto_whitebalance_mode: AutoWhiteBalanceMode = AutoWhiteBalanceMode.AUTO
    manual_whitebalance: Annotated[int, Field(strict=True, ge=1000, le=12000)]

    @classmethod
    def from_camera_control(cls, ctrl: dai.CameraControl):
        raw_ctrl = ctrl.get()
        properties = {
            "contrast": raw_ctrl.contrast,
            "brightness": raw_ctrl.brightness,
            "saturation": raw_ctrl.saturation,
            "chroma_denoise": raw_ctrl.chromaDenoise,
            "luma_denoise": raw_ctrl.lumaDenoise,
            "exposure_time": 1,
            "sensitivity_iso": 850,
            "auto_exposure_enable": ctrl.getExposureTime().total_seconds() == 0,
            "auto_exposure_limit": raw_ctrl.aeMaxExposureTimeUs,
            "auto_exposure_compensation": raw_ctrl.expCompensation,
            "auto_exposure_lock": raw_ctrl.aeLockMode,
            "auto_whitebalance_lock": raw_ctrl.awbLockMode,
            "manual_whitebalance": 6500,
        }

        return cls.model_validate(properties)

    def to_camera_control(self) -> dai.CameraControl:
        ctrl = dai.CameraControl()
        ctrl.setContrast(self.contrast)
        ctrl.setBrightness(self.brightness)
        ctrl.setSaturation(self.saturation)
        ctrl.setChromaDenoise(self.chroma_denoise)
        ctrl.setLumaDenoise(self.luma_denoise)

        if self.auto_exposure_enable:
            ctrl.setAutoExposureEnable()
            ctrl.setAutoExposureLimit(self.auto_exposure_limit)
            ctrl.setAutoExposureCompensation(self.auto_exposure_compensation)
            ctrl.setAutoExposureLock(self.auto_exposure_lock)
        elif self.exposure_time > 0:
            ctrl.setManualExposure(self.exposure_time, self.sensitivity_iso)

        if self.auto_whitebalance_mode != AutoWhiteBalanceMode.OFF:
            ctrl.setAutoWhiteBalanceLock(self.auto_whitebalance_lock)
            ctrl.setAutoWhiteBalanceMode(
                dai.RawCameraControl.AutoWhiteBalanceMode.__members__[
                    self.auto_whitebalance_mode.name
                ]
            )
        else:
            ctrl.setManualWhiteBalance(self.manual_whitebalance)

        return ctrl
