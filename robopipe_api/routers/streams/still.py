import anyio.to_thread

from ..common import SensorDep
from . import JpegResponse, stream_router


@stream_router.get(
    "/still",
    response_description="Image bytes in JPEG format",
    response_class=JpegResponse,
    responses={
        200: {
            "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}}
            },
            "description": "Image bytes in JPEG format",
        }
    },
)
async def capture_still_image(sensor: SensorDep) -> JpegResponse:
    img = await anyio.to_thread.run_sync(sensor.capture_still)

    return JpegResponse(img.getData().tobytes())
