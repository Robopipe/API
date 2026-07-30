from uuid import uuid4

import anyio.to_thread
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from ..recording.recorder import recorder_manager_factory
from ..recording.storage import list_segments, purge_tmp, stitch_segments, tmp_dir
from .common import Mxid

router = APIRouter(prefix="/cameras/{mxid}", tags=["recording"])


def _stitch(mxid: str):
    purge_tmp()
    segments = list_segments(mxid)
    if not segments:
        return None, 0
    directory = tmp_dir()
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f"{mxid}-{uuid4().hex}.webm"
    muxed = stitch_segments(segments, out_path)
    if muxed == 0:
        out_path.unlink(missing_ok=True)
        return None, 0
    return out_path, muxed


@router.get("/recording", response_class=FileResponse)
async def get_recording(mxid: Mxid):
    """Download the rolling recording of the camera's main sensor as a single
    WebM file covering up to the configured duration, ending at the request
    moment. Served purely from disk, so it also works for cameras that are no
    longer connected."""
    # Rotate-on-request: finalize the in-progress segment so the returned
    # video runs up to now. No-op when recording is disabled or the camera
    # has no live recorder.
    await recorder_manager_factory().flush(mxid)
    out_path, _ = await anyio.to_thread.run_sync(_stitch, mxid)
    if out_path is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"No recording found for camera {mxid}"
        )
    return FileResponse(
        path=out_path,
        media_type="video/webm",
        filename=f"recording-{mxid}.webm",
        background=BackgroundTask(out_path.unlink, missing_ok=True),
    )
