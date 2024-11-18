import depthai as dai

import dataclasses
import datetime


@dataclasses.dataclass
class SensorControl:
    exposure_time: datetime.timedelta
    # lens_position: int
    # sensitivity: int
    # # anti_banding_mode
    # auto_exporuse_compensation: int = 0
    # # auto_exposure_enable: bool
    # auto_exposure_lock: bool = False
    # auto_exposure_region: tuple[int, int, int, int]
    # # auto_focus_lens_range
    # # auto_focus_mode
    # # auto_focus_region
    # # auto_focus_trigger
    # auto_white_balance_lock: bool
    # # auto_white_balance_mode
    # brightness: int = 0
    # chroma_denoise: int = 1
    # contrast: int = 0
    # # control_mode
    # # effect_mode
    # # external_trigger
    # # frame_sync_mode
    # luma_denoise: int = 1
    # manual_focus: int
    # manual_white_balance: int
    # saturation: int = 0
    # # scene_mode
    # sharpness: int = 1
    # streaming: bool = True

    @classmethod
    def from_camera_control(cls, ctrl: dai.CameraControl):
        raw_ctrl = ctrl.get()

        return cls(ctrl.getExposureTime())

    # def to_camera_control(self) -> dai.CameraControl:
    #     ctrl = dai.CameraControl()
    #     ctrl.setContrast(self.contrast)

    #     return ctrl
