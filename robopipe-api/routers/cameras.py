from fastapi import APIRouter

from ..camera.device_info import DeviceInfo
from .common import CameraManagerDep, Mxid, CameraDep

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/")
def list_cameras(camera_manager: CameraManagerDep) -> list[DeviceInfo]:
    return list(map(lambda x: x.info, camera_manager.cameras.values()))


@router.get("/{mxid}")
def get_camera(camera: CameraDep) -> DeviceInfo:
    return camera.info


@router.post("/{mxid}")
def create_camera(camera_manager: CameraManagerDep, mxid: Mxid) -> DeviceInfo:
    camera_manager.boot_camera(mxid)

    return {"status": "ok"}


@router.delete("/{mxid}")
def delete_camera(camera_manager: CameraManagerDep, mxid: Mxid) -> DeviceInfo:
    camera_manager.shutdown_camera(mxid)

    return {"status": "ok"}


@router.get("/{mxid}/stats")
def get_camera_stats(camera: CameraDep):
    return camera.stats
