from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(
    prefix="/cameras/{mxid}/streams",
    tags=["streams"],
    responses={404: {"description": "Camera not found"}},
)

stream_router = APIRouter(
    prefix="/{stream_name}",
    tags=["streams"],
    responses={404: {"description": "Camera or stream not found"}},
)


class JpegResponse(Response):
    media_type = "image/jpeg"


from . import lifecycle  # noqa: E402, F401
from . import still  # noqa: E402, F401
from . import nn  # noqa: E402, F401
from . import video  # noqa: E402, F401
from . import dashboard  # noqa: E402, F401
from . import replay  # noqa: E402, F401

router.include_router(stream_router)

__all__ = ["router", "stream_router", "JpegResponse"]
