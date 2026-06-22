import depthai as dai
from pydantic import Field

from typing import Annotated, Literal

from ..camera.sensor.sensor_control import (
    AntiBandingMode,
    AutoFocusMode,
    AutoWhiteBalanceMode,
    SensorControl,
)
from .base_model import BaseModel


class SensorControlUpdate(SensorControl):
    __annotations__ = {
        k: Annotated[v, Field(default=None)]
        for k, v in SensorControl.__annotations__.items()
    }


SensorType = Literal["COLOR", "MONO", "THERMAL", "TOF"]


class ControlRange(BaseModel):
    min: float
    max: float
    default: float
    step: float | None = None


class SensorControlCapabilities(BaseModel):
    sensor_type: SensorType
    has_autofocus: bool
    has_color_controls: bool

    contrast: ControlRange
    sharpness: ControlRange
    luma_denoise: ControlRange
    exposure_time: ControlRange
    sensitivity_iso: ControlRange
    auto_exposure_compensation: ControlRange
    auto_exposure_limit: ControlRange

    saturation: ControlRange | None = None
    chroma_denoise: ControlRange | None = None
    manual_whitebalance: ControlRange | None = None
    lens_position: ControlRange | None = None

    auto_focus_modes: list[str] = Field(default_factory=list)
    auto_whitebalance_modes: list[str] | None = None
    anti_banding_modes: list[str] = Field(
        default_factory=lambda: [m.name for m in AntiBandingMode]
    )

    @classmethod
    def from_features(
        cls, features: dai.CameraFeatures
    ) -> "SensorControlCapabilities":
        supported_types = list(features.supportedTypes)
        if dai.CameraSensorType.COLOR in supported_types:
            sensor_type: SensorType = "COLOR"
        elif dai.CameraSensorType.MONO in supported_types:
            sensor_type = "MONO"
        elif dai.CameraSensorType.THERMAL in supported_types:
            sensor_type = "THERMAL"
        elif dai.CameraSensorType.TOF in supported_types:
            sensor_type = "TOF"
        else:
            sensor_type = "MONO"

        is_color = sensor_type == "COLOR"
        has_af = bool(features.hasAutofocusIC)

        return cls(
            sensor_type=sensor_type,
            has_autofocus=has_af,
            has_color_controls=is_color,
            contrast=ControlRange(min=-10, max=10, default=0, step=1),
            sharpness=ControlRange(min=0, max=4, default=1, step=1),
            luma_denoise=ControlRange(min=0, max=4, default=1, step=1),
            exposure_time=ControlRange(
                min=1, max=33_000_000, default=20_000, step=1
            ),
            sensitivity_iso=ControlRange(min=100, max=1600, default=800, step=1),
            auto_exposure_compensation=ControlRange(
                min=-9, max=9, default=0, step=1
            ),
            auto_exposure_limit=ControlRange(
                min=1, max=33_000_000, default=33_000, step=1
            ),
            saturation=(
                ControlRange(min=-10, max=10, default=0, step=1) if is_color else None
            ),
            chroma_denoise=(
                ControlRange(min=0, max=4, default=1, step=1) if is_color else None
            ),
            manual_whitebalance=(
                ControlRange(min=1000, max=12000, default=6500, step=100)
                if is_color
                else None
            ),
            lens_position=(
                ControlRange(min=0.0, max=1.0, default=0.5, step=0.01)
                if has_af
                else None
            ),
            auto_focus_modes=[m.name for m in AutoFocusMode] if has_af else [],
            auto_whitebalance_modes=(
                [m.name for m in AutoWhiteBalanceMode] if is_color else None
            ),
        )

    def unsupported_fields(self, update: dict) -> list[str]:
        unsupported: list[str] = []
        color_only = {
            "saturation",
            "chroma_denoise",
            "auto_whitebalance_mode",
            "auto_whitebalance_lock",
            "manual_whitebalance",
        }
        if not self.has_color_controls:
            unsupported.extend(sorted(color_only & set(update.keys())))
        if not self.has_autofocus and update.get("focus") is not None:
            unsupported.append("focus")
        return unsupported
