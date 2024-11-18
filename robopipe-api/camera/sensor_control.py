import depthai as dai

import dataclasses
import math


@dataclasses.dataclass
class SensorControl:
    exposure_time: int
    sensitivity_iso: int
    auto_exposure_enable: bool
    auto_exposure_compensation: int
    auto_exposure_limit: int
    auto_exposure_lock: bool
    contrast: int
    brightness: int
    saturation: int
    chroma_denoise: int
    luma_denoise: int

    @classmethod
    def from_camera_control(cls, ctrl: dai.CameraControl):
        raw_ctrl = ctrl.get()
        properties = {
            "contrast": raw_ctrl.contrast,
            "brightness": raw_ctrl.brightness,
            "saturation": raw_ctrl.saturation,
            "chroma_denoise": raw_ctrl.chromaDenoise,
            "luma_denoise": raw_ctrl.lumaDenoise,
            "exposure_time": math.floor(ctrl.getExposureTime().total_seconds() * 1000),
            "sensitivity_iso": ctrl.getSensitivity(),
            "auto_exposure_enable": ctrl.getExposureTime().total_seconds() == 0,
            "auto_exposure_limit": raw_ctrl.aeMaxExposureTimeUs,
            "auto_exposure_compensation": raw_ctrl.expCompensation,
            "auto_exposure_lock": raw_ctrl.aeLockMode,
        }

        return cls(**properties)

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

        return ctrl
