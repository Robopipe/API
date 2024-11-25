from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from contextlib import asynccontextmanager

from .camera.camera_manager import CameraManager
from .error import (
    CameraNotFoundException,
    SensorNotFoundException,
)
from .routers import cameras, sensors
from .stream import StreamService


@asynccontextmanager
async def lifespan(app: FastAPI):

    camera_manager = CameraManager()
    camera_manager.boot_cameras()
    stream_service = StreamService()

    yield

    stream_service.stop()


app = FastAPI(
    lifespan=lifespan,
    title="Robopipe API",
    description="API for the Robopipe application",
)

app.include_router(cameras.router)
app.include_router(sensors.router)


@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (CameraNotFoundException, SensorNotFoundException)):
        return JSONResponse(status_code=404, content=None)
