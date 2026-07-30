"""Always-on rolling video recording.

One CameraRecorder per connected camera subscribes permanently to the shared
WebRTC VideoTrack (via MediaRelay), which keeps the VP8 encode alive even
with no browser viewers, and muxes the packets into rolling ~15 s WebM
segments under get_data_dir()/recordings/{mxid}/. The oldest segments are
deleted to keep the total under ROBOPIPE_RECORDING_MAX_DURATION_SECONDS.

The VideoTrack does not survive device restarts — on any stream error it
stops itself and drops the track/relay caches — so the recorder re-creates
both through the factories with backoff.
"""

import os
import time
from functools import lru_cache
from pathlib import Path

import anyio
import anyio.to_thread
import av
import depthai as dai
from aiortc import MediaStreamError

from ..camera.camera import Camera
from ..camera.camera_manager import CameraManager, camera_manager_factory
from ..log import logger
from ..video_track import media_relay_factory, video_track_factory
from .storage import (
    SEGMENT_TIME_BASE,
    WEBM_OPTIONS,
    adopt_stale_parts,
    enforce_cap,
    part_name,
    purge_tmp,
    recordings_dir,
    segment_name,
    tmp_dir,
)

SEGMENT_TARGET_SECONDS = 15.0
RECONCILE_INTERVAL_SECONDS = 5.0
BACKOFF_START_SECONDS = 1.0
BACKOFF_MAX_SECONDS = 30.0
FLUSH_TIMEOUT_SECONDS = 2.0


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in ("true", "1", "yes")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %s", name, raw, default)
        return default


def _vp8_dimensions(payload: bytes) -> tuple[int, int]:
    """Width/height from a VP8 keyframe: 3-byte frame tag, start code
    9D 01 2A, then two le16 values whose low 14 bits are the dimensions."""
    if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
        raise ValueError("Not a VP8 keyframe")
    width = (payload[6] | (payload[7] << 8)) & 0x3FFF
    height = (payload[8] | (payload[9] << 8)) & 0x3FFF
    return width, height


class SegmentWriter:
    """Muxes VP8 packets into one .webm.part file. Fully synchronous — the
    recorder runs every method in a worker thread."""

    def __init__(self, mxid_dir: Path, first_packet: av.Packet):
        self.start_ms = int(time.time() * 1000)
        self.path = mxid_dir / part_name(self.start_ms)
        width, height = _vp8_dimensions(bytes(first_packet))
        self._container = av.open(
            str(self.path), "w", format="webm", options=WEBM_OPTIONS
        )
        try:
            self._stream = self._container.add_stream("vp8", rate=30)
            self._stream.width = width
            self._stream.height = height
            self._stream.time_base = SEGMENT_TIME_BASE
            self._first_pts = first_packet.pts
            self._last_rel_ms = 0
            self.write(first_packet)
        except Exception:
            self._container.close()
            raise

    def write(self, pkt: av.Packet) -> None:
        # The relay hands the same packet object to every subscriber
        # (WebRTC senders included) — mutate a copy, never the original.
        copy = av.Packet(bytes(pkt))
        rel_ms = int((pkt.pts - self._first_pts) * pkt.time_base / SEGMENT_TIME_BASE)
        copy.pts = copy.dts = rel_ms
        copy.time_base = SEGMENT_TIME_BASE
        copy.is_keyframe = pkt.is_keyframe
        copy.stream = self._stream
        self._container.mux(copy)
        self._last_rel_ms = rel_ms

    @property
    def duration_s(self) -> float:
        return self._last_rel_ms / 1000

    def finalize(self) -> Path:
        self._container.close()
        # fsync so the finalized segment survives an immediate power cut.
        fd = os.open(self.path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        final = self.path.parent / segment_name(self.start_ms, self._last_rel_ms)
        self.path.rename(final)
        return final


class CameraRecorder:
    """Records one camera's primary COLOR sensor into rolling segments."""

    def __init__(self, mxid: str, camera_manager: CameraManager, max_duration_s: float):
        self.mxid = mxid
        self._camera_manager = camera_manager
        self._max_duration_s = max_duration_s
        self._dir = recordings_dir(mxid)
        self._writer: SegmentWriter | None = None
        self._flush_lock = anyio.Lock()
        self._flush_requested = False
        self._flush_done = anyio.Event()
        self._segment_finalized = False

    async def run(self) -> None:
        await anyio.to_thread.run_sync(self._prepare_dir)
        backoff = BACKOFF_START_SECONDS
        while True:
            self._segment_finalized = False
            proxy = None
            try:
                proxy = self._subscribe()
                if proxy is not None:
                    while True:
                        packet = await proxy.recv()
                        await self._handle_packet(packet)
            except MediaStreamError:
                logger.info(f"Recorder {self.mxid}: video stream ended, will retry")
            except Exception as e:
                logger.warning(f"Recorder {self.mxid}: {e}")
            finally:
                if proxy is not None:
                    proxy.stop()
                with anyio.CancelScope(shield=True):
                    await self._finalize_writer()
            if self._segment_finalized:
                backoff = BACKOFF_START_SECONDS
            await anyio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX_SECONDS)

    def _prepare_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        adopt_stale_parts(self._dir)

    def _subscribe(self):
        camera = self._camera_manager.get(self.mxid)
        if camera is None:
            return None
        sensor_name = self._primary_color_sensor(camera)
        if sensor_name is None:
            return None
        track = video_track_factory(camera, sensor_name)
        # buffered=True: an unbounded per-subscriber queue, so slow disk
        # writes never drop packets (unlike the browsers' lossy proxies).
        return media_relay_factory(camera, sensor_name).subscribe(
            track, buffered=True
        )

    @staticmethod
    def _primary_color_sensor(camera: Camera) -> str | None:
        # Same COLOR filter as CameraManager.boot_camera; the stereo
        # pseudo-sensors have empty supportedTypes and fall out naturally.
        color = sorted(
            name
            for name, features in camera.all_sensors.items()
            if dai.CameraSensorType.COLOR in features.supportedTypes
        )
        return color[0] if color else None

    async def _handle_packet(self, pkt: av.Packet) -> None:
        if self._flush_requested:
            await self._finalize_writer()
            self._flush_requested = False
            self._flush_done.set()
        if self._writer is None:
            if not pkt.is_keyframe:
                return  # a WebM segment must start on a keyframe
            self._writer = await anyio.to_thread.run_sync(
                SegmentWriter, self._dir, pkt
            )
        elif pkt.is_keyframe and self._writer.duration_s >= SEGMENT_TARGET_SECONDS:
            await self._finalize_writer()
            self._writer = await anyio.to_thread.run_sync(
                SegmentWriter, self._dir, pkt
            )
        else:
            await anyio.to_thread.run_sync(self._writer.write, pkt)

    async def _finalize_writer(self) -> None:
        writer, self._writer = self._writer, None
        if writer is None:
            return
        try:
            await anyio.to_thread.run_sync(writer.finalize)
            self._segment_finalized = True
            await anyio.to_thread.run_sync(
                enforce_cap, self._dir, self._max_duration_s
            )
        except Exception as e:
            logger.warning(f"Recorder {self.mxid}: failed to finalize segment: {e}")

    async def flush(self, timeout: float = FLUSH_TIMEOUT_SECONDS) -> None:
        """Finalize the in-progress segment at the next packet so a retrieval
        includes footage up to the request moment. Times out (leaving the
        segment in place) when the recorder is stalled or dead."""
        async with self._flush_lock:
            if self._writer is None:
                return
            self._flush_done = anyio.Event()
            self._flush_requested = True
            with anyio.move_on_after(timeout):
                await self._flush_done.wait()
            self._flush_requested = False


class RecorderManager:
    """Starts/stops one CameraRecorder per connected camera."""

    def __init__(
        self, camera_manager: CameraManager, max_duration_s: float, enabled: bool
    ):
        self.enabled = enabled
        self._camera_manager = camera_manager
        self._max_duration_s = max_duration_s
        self._recorders: dict[str, tuple[CameraRecorder, anyio.CancelScope]] = {}

    async def run(self) -> None:
        await anyio.to_thread.run_sync(self._startup_maintenance)
        async with anyio.create_task_group() as tg:
            while True:
                self._reconcile(tg)
                await anyio.sleep(RECONCILE_INTERVAL_SECONDS)

    def _startup_maintenance(self) -> None:
        # Adopt crash leftovers for every camera ever recorded (orphans
        # included — they are the evidence) and drop stale stitched files.
        base = recordings_dir()
        base.mkdir(parents=True, exist_ok=True)
        tmp_dir().mkdir(parents=True, exist_ok=True)
        for mxid_dir in base.iterdir():
            if mxid_dir.is_dir() and mxid_dir != tmp_dir():
                adopt_stale_parts(mxid_dir)
        purge_tmp()

    def _reconcile(self, tg: anyio.abc.TaskGroup) -> None:
        connected = set(self._camera_manager.cameras.keys())
        for mxid in connected - self._recorders.keys():
            recorder = CameraRecorder(mxid, self._camera_manager, self._max_duration_s)
            scope = anyio.CancelScope()
            self._recorders[mxid] = (recorder, scope)
            tg.start_soon(self._run_recorder, recorder, scope)
        for mxid in self._recorders.keys() - connected:
            _, scope = self._recorders.pop(mxid)
            scope.cancel()

    async def _run_recorder(
        self, recorder: CameraRecorder, scope: anyio.CancelScope
    ) -> None:
        with scope:
            try:
                await recorder.run()
            except Exception:
                logger.exception(f"Recorder for {recorder.mxid} crashed")
        # If run() returned without being reconciled away (crash), drop the
        # entry so the next reconcile pass can start a fresh recorder.
        entry = self._recorders.get(recorder.mxid)
        if entry is not None and entry[0] is recorder:
            self._recorders.pop(recorder.mxid, None)

    async def flush(self, mxid: str) -> None:
        entry = self._recorders.get(mxid)
        if entry is not None:
            await entry[0].flush()


@lru_cache(maxsize=1)
def recorder_manager_factory() -> RecorderManager:
    return RecorderManager(
        camera_manager=camera_manager_factory(),
        max_duration_s=_env_float("ROBOPIPE_RECORDING_MAX_DURATION_SECONDS", 600.0),
        enabled=_env_bool("ROBOPIPE_RECORDING_ENABLED", False),
    )
