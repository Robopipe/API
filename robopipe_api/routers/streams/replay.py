import uuid
from pathlib import Path
from urllib.parse import urlparse

import anyio.to_thread
import httpx
from fastapi import HTTPException, Request, UploadFile, status

from ...paths import get_data_dir
from ..common import CameraDep, StreamName
from . import stream_router

REPLAY_UPLOAD_CHUNK_SIZE = 1 << 20  # 1 MiB


async def _write_request_stream(request: Request, dest: Path) -> None:
    f = await anyio.to_thread.run_sync(lambda: dest.open("wb"))
    try:
        async for chunk in request.stream():
            if chunk:
                await anyio.to_thread.run_sync(f.write, chunk)
    finally:
        await anyio.to_thread.run_sync(f.close)


async def _write_upload_file(video: UploadFile, dest: Path) -> None:
    f = await anyio.to_thread.run_sync(lambda: dest.open("wb"))
    try:
        while True:
            chunk = await video.read(REPLAY_UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            await anyio.to_thread.run_sync(f.write, chunk)
    finally:
        await anyio.to_thread.run_sync(f.close)


async def _download_url_to_file(source_url: str, dest: Path) -> None:
    f = await anyio.to_thread.run_sync(lambda: dest.open("wb"))
    try:
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", source_url) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(REPLAY_UPLOAD_CHUNK_SIZE):
                    if chunk:
                        await anyio.to_thread.run_sync(f.write, chunk)
    finally:
        await anyio.to_thread.run_sync(f.close)


@stream_router.post("/replay", status_code=status.HTTP_201_CREATED)
async def add_replay_video(
    request: Request,
    camera: CameraDep,
    stream_name: StreamName,
    filename: str | None = None,
):
    replay_dir = get_data_dir() / "replay_videos"
    replay_dir.mkdir(parents=True, exist_ok=True)

    content_type = request.headers.get("content-type", "")
    is_multipart = content_type.startswith("multipart/form-data")
    is_json = content_type.startswith("application/json")

    video: UploadFile | None = None
    source_url: str | None = None
    if is_json:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="JSON body must be an object",
            )
        source_url = payload.get("url")
        if not isinstance(source_url, str) or not source_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing 'url' field in JSON body",
            )
        explicit_name = payload.get("filename")
        source_name = (
            explicit_name if isinstance(explicit_name, str) and explicit_name
            else urlparse(source_url).path
        )
    elif is_multipart:
        form = await request.form()
        form_video = form.get("video")
        if not isinstance(form_video, UploadFile):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing 'video' file field",
            )
        video = form_video
        source_name = video.filename
    else:
        source_name = filename

    extension = Path(source_name).suffix if source_name else ".mp4"
    file_path = replay_dir / f"{uuid.uuid4().hex}{extension}"

    try:
        if source_url is not None:
            await _download_url_to_file(source_url, file_path)
        elif video is not None:
            await _write_upload_file(video, file_path)
        else:
            await _write_request_stream(request, file_path)
    except httpx.HTTPError as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to download replay video from URL: {e}",
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    try:
        camera.add_replay_video(stream_name, str(file_path))
    except (ValueError, RuntimeError):
        file_path.unlink(missing_ok=True)
        raise


@stream_router.delete("/replay", status_code=status.HTTP_202_ACCEPTED)
def remove_replay_video(camera: CameraDep, stream_name: StreamName):
    camera.remove_replay_video(stream_name)


@stream_router.get("/replay")
def get_replay_video(camera: CameraDep, stream_name: StreamName):
    from ...models.replay_info import ReplayInfo

    try:
        path = camera.get_replay_video(stream_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ReplayInfo(
        replay=path is not None,
        filename=Path(path).name if path is not None else None,
    )
