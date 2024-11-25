from fastapi import APIRouter

from ..camera.camera_stats import CameraStats
from ..camera.device_info import DeviceInfo
from .common import CameraManagerDep, Mxid, CameraDep

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/")
def list_cameras(camera_manager: CameraManagerDep) -> list[DeviceInfo]:
    return list(map(lambda x: x.info, camera_manager.cameras.values()))


camera_router = APIRouter(
    prefix="/{mxid}",
    tags=["cameras"],
    responses={404: {"description": "Camera not found"}},
)


@camera_router.get("/")
def get_camera(camera: CameraDep) -> DeviceInfo:
    return camera.info


@camera_router.post("/")
def create_camera(camera_manager: CameraManagerDep, mxid: Mxid) -> DeviceInfo:
    camera_manager.boot_camera(mxid)

    return {"status": "ok"}


@camera_router.delete("/")
def delete_camera(camera_manager: CameraManagerDep, mxid: Mxid) -> DeviceInfo:
    camera_manager.shutdown_camera(mxid)

    return {"status": "ok"}


@camera_router.get("/stats")
def get_camera_stats(camera: CameraDep) -> CameraStats:
    return camera.stats


router.include_router(camera_router)
