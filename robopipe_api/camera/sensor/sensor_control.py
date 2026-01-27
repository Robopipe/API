import depthai as dai
from pydantic import Field, ConfigDict

from enum import Enum
import math
from typing import Annotated

from ...models.base_model import BaseModel


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


class SensorFocus(BaseModel):
    auto_focus_mode: Annotated[
        AutoFocusMode, Field(default=AutoFocusMode.CONTINUOUS_VIDEO)
    ]
    auto_focus_trigger: Annotated[bool, Field(default=False)]
    lens_position: Annotated[float, Field(ge=0.0, le=1.0, default=0.0)]


class AutoWhiteBalanceMode(Enum):
    AUTO = dai.CameraControl.AutoWhiteBalanceMode.AUTO.name
    CLOUDY_DAYLIGHT = dai.CameraControl.AutoWhiteBalanceMode.CLOUDY_DAYLIGHT.name
    DAYLIGHT = dai.CameraControl.AutoWhiteBalanceMode.DAYLIGHT.name
    FLUORESCENT = dai.CameraControl.AutoWhiteBalanceMode.FLUORESCENT.name
    INCANDESCENT = dai.CameraControl.AutoWhiteBalanceMode.INCANDESCENT.name
    OFF = dai.CameraControl.AutoWhiteBalanceMode.OFF.name
    SHADE = dai.CameraControl.AutoWhiteBalanceMode.SHADE.name
    TWILIGHT = dai.CameraControl.AutoWhiteBalanceMode.TWILIGHT.name
    WARM_FLUORESCENT = dai.CameraControl.AutoWhiteBalanceMode.WARM_FLUORESCENT.name


class SensorControl(BaseModel):
    exposure_time: Annotated[
        int,
        Field(
            description="Exposure time in microseconds. Ignored if auto_exposure_enable is set to true.",
        ),
    ]
    sensitivity_iso: Annotated[
        int,
        Field(),
    ]
    auto_exposure_enable: bool
    auto_exposure_compensation: Annotated[int, Field()]
    auto_exposure_limit: Annotated[
        int,
        Field(
            description="Maximum exposure time limit for auto-exposure in microseconds"
        ),
    ]
    auto_exposure_lock: bool
    contrast: Annotated[int, Field()]
    brightness: Annotated[int, Field()]
    saturation: Annotated[int, Field()]
    chroma_denoise: Annotated[int, Field()]
    luma_denoise: Annotated[int, Field()]
    auto_whitebalance_lock: bool
    auto_whitebalance_mode: AutoWhiteBalanceMode = AutoWhiteBalanceMode.AUTO
    manual_whitebalance: Annotated[int, Field(ge=1000, le=12000)]
    focus: Annotated[SensorFocus | None, Field(default=None)]

    model_config = ConfigDict(revalidate_instances="always")

    @classmethod
    def from_camera_control(cls, ctrl: dai.CameraControl, has_af: bool):
        print(ctrl)
        properties = {
            "contrast": ctrl.contrast,
            "brightness": ctrl.brightness,
            "saturation": ctrl.saturation,
            "chroma_denoise": ctrl.chromaDenoise,
            "luma_denoise": ctrl.lumaDenoise,
            "exposure_time": math.floor(
                ctrl.getExposureTime().total_seconds() * 1000000
            ),
            "sensitivity_iso": ctrl.getSensitivity(),
            "auto_exposure_enable": ctrl.getExposureTime().total_seconds() == 0,
            "auto_exposure_limit": ctrl.aeMaxExposureTimeUs,
            "auto_exposure_compensation": ctrl.expCompensation,
            "auto_exposure_lock": ctrl.aeLockMode,
            "auto_whitebalance_lock": ctrl.awbLockMode,
            "manual_whitebalance": 6500,
            "focus": SensorFocus() if has_af else None,
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
                dai.CameraControl.AutoWhiteBalanceMode.__members__[
                    self.auto_whitebalance_mode.name
                ]
            )
        else:
            ctrl.setManualWhiteBalance(self.manual_whitebalance)

        if self.focus is not None:
            ctrl.setAutoFocusMode(self.focus.auto_focus_mode.to_dai_af_mode())

            if self.focus.auto_focus_trigger:
                ctrl.setAutoFocusTrigger()

            if self.focus.auto_focus_mode == AutoFocusMode.OFF:
                ctrl.setManualFocusRaw(self.focus.lens_position)

        return ctrl
