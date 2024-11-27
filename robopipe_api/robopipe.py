from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from contextlib import asynccontextmanager
import os

from .camera.camera_manager import camera_manager_factory
from .error import (
    CameraNotFoundException,
    SensorNotFoundException,
)
from .routers import cameras, sensors
from .stream import stream_service_factory


@asynccontextmanager
async def lifespan(app: FastAPI):

    camera_manager = camera_manager_factory()
    camera_manager.boot_cameras()
    stream_service = stream_service_factory(camera_manager)

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


def setup():
    load_dotenv()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=(os.environ.get("CORS_ORIGINS") or "*").split(","),
        allow_credentials=True,
        allow_methods=(os.environ.get("CORS_METHODS") or "*").split(","),
        allow_headers=(os.environ.get("CORS_HEADERS") or "*").split(","),
    )


setup()


def main():
    uvicorn.run(
        app,
        host=os.environ.get("HOST") or "0.0.0.0",
        port=int(os.environ.get("PORT") or "8080"),
    )
