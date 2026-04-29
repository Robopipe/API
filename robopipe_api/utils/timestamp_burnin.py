"""Burn the source-frame device timestamp into the top strip of an
av.VideoFrame so it can be recovered by a downstream consumer (the browser)
after H.264 encode -> decode. The matching detection message carries the
same ts_us, allowing pixel-perfect synchronization between WebRTC video
and inference output without relying on parser-internal seq numbering.

Layout (left-to-right, MSB first), 48 bits total:
    magic(8) | ts_lo32(32) | crc8(8)

Each bit is rendered as a (block x block) square of 0 or 255 in the Y
plane. block = max(MIN_BLOCK, frame_width // (TOTAL_BITS * 2)). The strip
height is `block` rows.

Lower 32 bits of ts_us wrap every ~71.5 min — fine given the matcher's
sub-second eviction window.
"""

import av
import numpy as np

MAGIC = 0xA5
TS_BITS = 32
CRC_BITS = 8
TOTAL_BITS = 8 + TS_BITS + CRC_BITS  # 48
MIN_BLOCK = 4

_SUPPORTED_FORMATS = ("gray", "nv12", "yuv420p", "bgr24")


def pick_block_size(width: int) -> int:
    return max(MIN_BLOCK, width // (TOTAL_BITS * 5))


def _crc8(value: int, n_bytes: int) -> int:
    """CRC-8 with poly 0x07, init 0, MSB-first over the high `n_bytes` bytes."""
    crc = 0
    for i in range(n_bytes - 1, -1, -1):
        crc ^= (value >> (i * 8)) & 0xFF
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc


def encode_payload(ts_us: int) -> int:
    ts32 = ts_us & 0xFFFFFFFF
    framing = (MAGIC << TS_BITS) | ts32  # 40 bits: magic + ts
    crc = _crc8(framing, 5)
    return (framing << CRC_BITS) | crc


def burn_timestamp(frame: av.VideoFrame, ts_us: int) -> av.VideoFrame:
    """Return a new VideoFrame with ts_us burned into its top strip.
    On unsupported formats or frames too small to fit the strip, returns the
    input frame unchanged."""
    fmt = frame.format.name
    if fmt not in _SUPPORTED_FORMATS:
        return frame

    width = frame.width
    height = frame.height
    block = pick_block_size(width)
    if block * TOTAL_BITS > width or block > height:
        return frame

    arr = frame.to_ndarray()
    payload = encode_payload(ts_us)
    is_packed = fmt == "bgr24"
    for i in range(TOTAL_BITS):
        bit = (payload >> (TOTAL_BITS - 1 - i)) & 1
        x0 = i * block
        x1 = x0 + block
        value = 255 if bit else 0
        if is_packed:
            arr[0:block, x0:x1, :] = value
        else:
            arr[0:block, x0:x1] = value

    return av.VideoFrame.from_ndarray(arr, format=fmt)


def decode_payload(strip: np.ndarray, width: int) -> int | None:
    """Decode ts_us from the top strip of a Y-plane image. Returns None on
    magic or CRC mismatch. `strip` is uint8 of shape (>=block, >=block*TOTAL_BITS).

    Used in tests and as a Python reference for the JS decoder.
    """
    block = pick_block_size(width)
    if strip.shape[0] < block or strip.shape[1] < block * TOTAL_BITS:
        return None

    payload = 0
    for i in range(TOTAL_BITS):
        x0 = i * block
        x1 = x0 + block
        # Threshold the mean of the block at 128.
        bit = 1 if strip[0:block, x0:x1].mean() >= 128 else 0
        payload = (payload << 1) | bit

    magic = (payload >> (TS_BITS + CRC_BITS)) & 0xFF
    if magic != MAGIC:
        return None
    crc_seen = payload & ((1 << CRC_BITS) - 1)
    framing = payload >> CRC_BITS
    if _crc8(framing, 5) != crc_seen:
        return None
    return framing & 0xFFFFFFFF
