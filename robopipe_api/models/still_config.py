from enum import Enum

from .base_model import BaseModel


class ImgResizeMode(str, Enum):
    CROP = "CROP"
    STRETCH = "STRETCH"
    LETTERBOX = "LETTERBOX"


class StillConfig(BaseModel):
    width: int
    height: int
    fps: int
    resize_mode: ImgResizeMode = ImgResizeMode.CROP


class StillConfigOption(BaseModel):
    width: int
    height: int
    min_fps: int
    max_fps: int
