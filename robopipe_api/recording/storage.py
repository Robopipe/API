"""On-disk layout and stitching for rolling camera recordings.

Deliberately free of camera/DepthAI imports so the retrieval endpoint can
serve recordings of cameras that are no longer connected.

Layout: get_data_dir()/recordings/{mxid}/{start_ms:013d}_{dur_ms:08d}.webm
The segment currently being written uses {start_ms:013d}.webm.part and is
renamed on finalization. Segments from a previous run that were never
finalized (power cut, SIGKILL) are adopted at startup with a duration
estimated from the file's mtime.
"""

import time
from fractions import Fraction
from pathlib import Path

import av

from ..log import logger
from ..paths import get_data_dir

SEGMENT_SUFFIX = ".webm"
PART_SUFFIX = ".webm.part"
SEGMENT_TIME_BASE = Fraction(1, 1000)
# Bound power-cut data loss: start a new matroska cluster every second and
# push packets straight to the OS instead of buffering them in the muxer.
WEBM_OPTIONS = {"cluster_time_limit": "1000", "flush_packets": "1"}
# Gap inserted between stitched segments so pts stay strictly monotonic.
FRAME_HOP_MS = 33


def recordings_dir(mxid: str | None = None) -> Path:
    base = get_data_dir() / "recordings"
    return base / mxid if mxid is not None else base


def tmp_dir() -> Path:
    return recordings_dir() / ".tmp"


def segment_name(start_ms: int, dur_ms: int) -> str:
    return f"{start_ms:013d}_{dur_ms:08d}{SEGMENT_SUFFIX}"


def part_name(start_ms: int) -> str:
    return f"{start_ms:013d}{PART_SUFFIX}"


def parse_segment_name(path: Path) -> tuple[int, int | None] | None:
    """Return (start_ms, dur_ms) for a segment, (start_ms, None) for an
    in-progress .part file, or None for anything else."""
    name = path.name
    try:
        if name.endswith(PART_SUFFIX):
            return int(name[: -len(PART_SUFFIX)]), None
        if name.endswith(SEGMENT_SUFFIX):
            start, dur = name[: -len(SEGMENT_SUFFIX)].split("_")
            return int(start), int(dur)
    except ValueError:
        pass
    return None


def list_segments(mxid: str) -> list[Path]:
    """All segments (finalized + in-progress) for a camera, oldest first."""
    mxid_dir = recordings_dir(mxid)
    if not mxid_dir.is_dir():
        return []
    segments = [p for p in mxid_dir.iterdir() if parse_segment_name(p) is not None]
    return sorted(segments, key=lambda p: parse_segment_name(p)[0])


def adopt_stale_parts(mxid_dir: Path) -> None:
    """Finalize .part segments left behind by a crash/power cut, estimating
    their duration from the file mtime. Their readable prefix remains
    stitchable evidence."""
    for part in mxid_dir.glob(f"*{PART_SUFFIX}"):
        parsed = parse_segment_name(part)
        if parsed is None:
            continue
        start_ms = parsed[0]
        dur_ms = max(0, int(part.stat().st_mtime * 1000) - start_ms)
        try:
            part.rename(mxid_dir / segment_name(start_ms, dur_ms))
            logger.info(f"Adopted stale recording segment {part.name}")
        except OSError as e:
            logger.warning(f"Failed to adopt stale segment {part}: {e}")


def enforce_cap(mxid_dir: Path, max_duration_s: float) -> None:
    """Delete oldest finalized segments while the summed duration exceeds the
    cap. The newest segment is always kept so there is something to serve."""
    finalized = []
    for p in mxid_dir.glob(f"*{SEGMENT_SUFFIX}"):
        parsed = parse_segment_name(p)
        if parsed is not None and parsed[1] is not None:
            finalized.append((parsed[0], parsed[1], p))
    finalized.sort()

    total_ms = sum(dur for _, dur, _ in finalized)
    max_ms = max_duration_s * 1000
    for _, dur, path in finalized[:-1]:
        if total_ms <= max_ms:
            break
        try:
            path.unlink()
            total_ms -= dur
        except OSError as e:
            logger.warning(f"Failed to delete old segment {path}: {e}")


def purge_tmp(older_than_s: float = 3600) -> None:
    """Delete stitched temp files left behind by interrupted downloads."""
    directory = tmp_dir()
    if not directory.is_dir():
        return
    cutoff = time.time() - older_than_s
    for p in directory.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError as e:
            logger.warning(f"Failed to purge temp recording {p}: {e}")


def stitch_segments(seg_paths: list[Path], out_path: Path) -> int:
    """Remux segments into one WebM at out_path, oldest first, without
    re-encoding. Unreadable segments (power-cut garbage) are skipped and a
    corrupt tail only costs the packets after the damage point. Returns the
    number of packets muxed."""
    total_packets = 0
    offset_ms = 0
    out = av.open(str(out_path), "w", format="webm")
    out_stream = None
    try:
        for seg_path in seg_paths:
            try:
                inp = av.open(str(seg_path))
            except Exception as e:
                logger.warning(f"Skipping unreadable segment {seg_path.name}: {e}")
                continue

            muxed = 0
            last_rel_ms = 0
            try:
                in_stream = inp.streams.video[0]
                if out_stream is None:
                    out_stream = out.add_stream_from_template(in_stream)
                    out_stream.time_base = SEGMENT_TIME_BASE
                first_pts = None
                for pkt in inp.demux(in_stream):
                    if pkt.dts is None:  # demuxer flush packet
                        continue
                    if first_pts is None:
                        if not pkt.is_keyframe:
                            continue  # decoders can't start mid-GOP
                        first_pts = pkt.pts
                    rel_ms = int(
                        (pkt.pts - first_pts) * pkt.time_base / SEGMENT_TIME_BASE
                    )
                    pkt.stream = out_stream
                    pkt.pts = pkt.dts = offset_ms + rel_ms
                    pkt.time_base = SEGMENT_TIME_BASE
                    out.mux(pkt)
                    muxed += 1
                    last_rel_ms = rel_ms
            except Exception as e:
                logger.warning(
                    f"Segment {seg_path.name} truncated after {muxed} packets: {e}"
                )
            finally:
                inp.close()

            if muxed:
                total_packets += muxed
                offset_ms += last_rel_ms + FRAME_HOP_MS
    finally:
        # Unclosed OutputContainers can crash the process at GC time.
        out.close()

    return total_packets
