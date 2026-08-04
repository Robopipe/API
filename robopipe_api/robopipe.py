import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from contextlib import asynccontextmanager
from importlib.metadata import version
import os
from pathlib import Path


from .camera.camera_manager import camera_manager_factory
from .controller.config import EvokConfig, HWDict, create_devices
from .controller.devices import Devices, RUN, OWBUS, TCPBUS, SERIALBUS, MODBUS_SLAVE
from .dashboard.cleanup_task import cleanup_task_factory
from .dashboard.events_store import events_store_factory
from .dashboard.reports_store import reports_store_factory
from .dashboard.sync_task import sync_task_factory
from .error import (
    CameraNotFoundException,
    SensorNotFoundException,
)
from .routers import cameras, controller, recording, reports, streams
from .discovery import DEFAULT_API_PORT, discovery_manager_factory
from .recording.recorder import recorder_manager_factory
from .stream import stream_service_factory
from .webrtc_manager import webrtc_manager_factory
from . import __version__


def setup():
    load_dotenv(os.getenv("ROBOPIPE_API_ENV"), override=True)


setup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    camera_manager = camera_manager_factory()
    camera_manager.boot_cameras()
    stream_service = stream_service_factory(camera_manager)
    webrtc_manager = webrtc_manager_factory()
    controller_config_path = os.getenv("CONTROLLER_CONFIG")

    events_store = events_store_factory()
    events_store.init()
    reports_store_factory().reset_stuck_reports()
    sync_task = sync_task_factory()
    cleanup_task = cleanup_task_factory()
    recorder_manager = recorder_manager_factory()

    discovery_manager = discovery_manager_factory()
    await discovery_manager.start()

    async with anyio.create_task_group() as tg:
        tg.start_soon(sync_task.run)
        tg.start_soon(cleanup_task.run)
        tg.start_soon(discovery_manager.run_udp)

        if recorder_manager.enabled:
            tg.start_soon(recorder_manager.run)

        if controller_config_path is not None and os.path.exists(controller_config_path):
            hw_dict = HWDict([f"{controller_config_path}/hw_definitions/"])
            controller_config = EvokConfig(controller_config_path)

            create_devices(controller_config, hw_dict)
            Devices.register_device(RUN, Devices.aliases)

            for owbus in Devices.by_int(OWBUS):
                tg.start_soon(owbus.bus_driver.switch_to_async)

            for bustype in [TCPBUS, SERIALBUS]:
                for device in Devices.by_int(bustype):
                    tg.start_soon(device.switch_to_async)

            for modbus_slave in Devices.by_int(MODBUS_SLAVE):
                tg.start_soon(modbus_slave.switch_to_async)

                if modbus_slave.scan_enabled:
                    tg.start_soon(modbus_slave.start_scanning)

        yield

        tg.cancel_scope.cancel()

    await discovery_manager.stop()
    stream_service.stop()
    await webrtc_manager.remove_all_pcs()


app = FastAPI(
    lifespan=lifespan,
    title="Robopipe API",
    version=__version__,
    description="API for the Robopipe application",
    servers=[
        {
            "url": f"http://localhost:{os.getenv('PORT') or str(DEFAULT_API_PORT)}",
            "description": "Locally running server",
        },
    ],
)

controller_hostname = os.getenv("HOSTNAME")

if controller_hostname is not None and controller_hostname.startswith("robopipe"):
    app.servers.insert(
        0,
        {
            "url": f"https://{controller_hostname}.local",
            "description": "Robopipe controller running on local network",
        },
    )

if os.getenv("GITHUB_ACTIONS") is not None:
    app.servers.insert(
        0,
        {
            "url": "https://robopipe-{controllerId}.local",
            "description": "Robopipe controller running on local network",
            "variables": {
                "controllerId": {
                    "default": "1",
                    "description": "Robopipe controller ID",
                }
            },
        },
    )

app.include_router(cameras.router)
app.include_router(streams.router)
app.include_router(recording.router)
app.include_router(reports.router)
controller.register_device_endpoints(controller.DEVICE_ENDPOINTS)
app.include_router(controller.router)

# Mount static files for stream viewer
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def hello_robopipe():
    return PlainTextResponse("Hello from Robopipe API!")


@app.exception_handler(CameraNotFoundException)
@app.exception_handler(SensorNotFoundException)
def not_found_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=404, content=None)


def app_setup():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=(os.getenv("CORS_ORIGINS") or "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app_setup()


def main():
    uvicorn.run(
        app,
        host=os.getenv("HOST") or "0.0.0.0",
        port=int(os.getenv("PORT") or str(DEFAULT_API_PORT)),
    )
