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

    def to_dai(self) -> dai.CameraControl.AutoFocusMode:
        return dai.CameraControl.AutoFocusMode.__members__[self.name]


class AutoWhiteBalanceMode(Enum):
    OFF = dai.CameraControl.AutoWhiteBalanceMode.OFF.name
    AUTO = dai.CameraControl.AutoWhiteBalanceMode.AUTO.name
    INCANDESCENT = dai.CameraControl.AutoWhiteBalanceMode.INCANDESCENT.name
    FLUORESCENT = dai.CameraControl.AutoWhiteBalanceMode.FLUORESCENT.name
    WARM_FLUORESCENT = dai.CameraControl.AutoWhiteBalanceMode.WARM_FLUORESCENT.name
    DAYLIGHT = dai.CameraControl.AutoWhiteBalanceMode.DAYLIGHT.name
    CLOUDY_DAYLIGHT = dai.CameraControl.AutoWhiteBalanceMode.CLOUDY_DAYLIGHT.name
    TWILIGHT = dai.CameraControl.AutoWhiteBalanceMode.TWILIGHT.name
    SHADE = dai.CameraControl.AutoWhiteBalanceMode.SHADE.name

    def to_dai(self) -> dai.CameraControl.AutoWhiteBalanceMode:
        return dai.CameraControl.AutoWhiteBalanceMode.__members__[self.name]


class AntiBandingMode(Enum):
    OFF = dai.CameraControl.AntiBandingMode.OFF.name
    MAINS_50_HZ = dai.CameraControl.AntiBandingMode.MAINS_50_HZ.name
    MAINS_60_HZ = dai.CameraControl.AntiBandingMode.MAINS_60_HZ.name
    AUTO = dai.CameraControl.AntiBandingMode.AUTO.name

    def to_dai(self) -> dai.CameraControl.AntiBandingMode:
        return dai.CameraControl.AntiBandingMode.__members__[self.name]


class SensorFocus(BaseModel):
    auto_focus_mode: Annotated[
        AutoFocusMode, Field(default=AutoFocusMode.CONTINUOUS_VIDEO)
    ]
    auto_focus_trigger: Annotated[bool, Field(default=False)]
    lens_position: Annotated[float, Field(ge=0.0, le=1.0, default=0.5)]


class SensorControl(BaseModel):
    # Exposure
    auto_exposure_enable: Annotated[bool, Field(default=True)]
    exposure_time: Annotated[
        int,
        Field(
            ge=1,
            le=33_000_000,
            default=20_000,
            description="Manual exposure time in microseconds. Applied only when auto_exposure_enable is False.",
        ),
    ]
    sensitivity_iso: Annotated[
        int,
        Field(
            ge=100,
            le=1600,
            default=800,
            description="Manual ISO. Applied only when auto_exposure_enable is False.",
        ),
    ]
    auto_exposure_compensation: Annotated[int, Field(ge=-9, le=9, default=0)]
    auto_exposure_limit: Annotated[
        int,
        Field(
            ge=1,
            le=33_000_000,
            default=33_000,
            description="Max exposure time (µs) used by auto-exposure.",
        ),
    ]
    auto_exposure_lock: Annotated[bool, Field(default=False)]

    # ISP
    contrast: Annotated[int, Field(ge=-10, le=10, default=0)]
    saturation: Annotated[int, Field(ge=-10, le=10, default=0)]
    sharpness: Annotated[int, Field(ge=0, le=4, default=1)]
    luma_denoise: Annotated[int, Field(ge=0, le=4, default=1)]
    chroma_denoise: Annotated[int, Field(ge=0, le=4, default=1)]

    # White balance (COLOR sensors only)
    auto_whitebalance_mode: Annotated[
        AutoWhiteBalanceMode, Field(default=AutoWhiteBalanceMode.AUTO)
    ]
    auto_whitebalance_lock: Annotated[bool, Field(default=False)]
    manual_whitebalance: Annotated[int, Field(ge=1000, le=12000, default=6500)]

    # Focus (sensors with hasAutofocusIC)
    focus: Annotated[SensorFocus | None, Field(default=None)]

    # Misc
    anti_banding_mode: Annotated[
        AntiBandingMode, Field(default=AntiBandingMode.MAINS_50_HZ)
    ]

    model_config = ConfigDict(revalidate_instances="always")

    @classmethod
    def default_for(cls, features: dai.CameraFeatures) -> "SensorControl":
        return cls(focus=SensorFocus() if features.hasAutofocusIC else None)

    def update_from_frame(self, img: dai.ImgFrame) -> None:
        self.exposure_time = max(
            1, math.floor(img.getExposureTime().total_seconds() * 1_000_000)
        )
        sensitivity = img.getSensitivity()
        if sensitivity > 0:
            self.sensitivity_iso = max(100, min(1600, sensitivity))
        color_temp = img.getColorTemperature()
        if 1000 <= color_temp <= 12000:
            self.manual_whitebalance = color_temp
        if self.focus is not None:
            lens_position_raw = img.getLensPositionRaw()
            if 0.0 <= lens_position_raw <= 1.0:
                self.focus.lens_position = lens_position_raw

    def to_camera_control(self, features: dai.CameraFeatures) -> dai.CameraControl:
        ctrl = dai.CameraControl()
        is_color = dai.CameraSensorType.COLOR in features.supportedTypes

        ctrl.setContrast(self.contrast)
        ctrl.setSharpness(self.sharpness)
        ctrl.setLumaDenoise(self.luma_denoise)
        if is_color:
            ctrl.setSaturation(self.saturation)
            ctrl.setChromaDenoise(self.chroma_denoise)

        if self.auto_exposure_enable:
            ctrl.setAutoExposureEnable()
            ctrl.setAutoExposureLimit(self.auto_exposure_limit)
            ctrl.setAutoExposureCompensation(self.auto_exposure_compensation)
            ctrl.setAutoExposureLock(self.auto_exposure_lock)
        else:
            ctrl.setManualExposure(self.exposure_time, self.sensitivity_iso)

        if is_color:
            if self.auto_whitebalance_mode != AutoWhiteBalanceMode.OFF:
                ctrl.setAutoWhiteBalanceMode(self.auto_whitebalance_mode.to_dai())
                ctrl.setAutoWhiteBalanceLock(self.auto_whitebalance_lock)
            else:
                ctrl.setManualWhiteBalance(self.manual_whitebalance)

        if self.focus is not None and features.hasAutofocusIC:
            ctrl.setAutoFocusMode(self.focus.auto_focus_mode.to_dai())
            if self.focus.auto_focus_mode == AutoFocusMode.OFF:
                ctrl.setManualFocusRaw(self.focus.lens_position)
            elif self.focus.auto_focus_trigger:
                ctrl.setAutoFocusTrigger()

        ctrl.setAntiBandingMode(self.anti_banding_mode.to_dai())
        return ctrl
