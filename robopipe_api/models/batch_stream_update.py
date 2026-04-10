import re

from pydantic import field_validator

from .base_model import BaseModel

STREAM_NAME_PATTERN = re.compile(r"^(CAM_[A-H]|DEPTH_[A-H]_[A-H])$")


class BatchStreamUpdate(BaseModel):
    activate: list[str] = []
    deactivate: list[str] = []

    @field_validator("activate", "deactivate", mode="before")
    @classmethod
    def validate_stream_names(cls, v: list[str]) -> list[str]:
        for name in v:
            if not STREAM_NAME_PATTERN.match(name):
                raise ValueError(
                    f"Invalid stream name '{name}'. "
                    "Must match CAM_[A-H] or DEPTH_[A-H]_[A-H]."
                )
        return v
