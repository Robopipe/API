/**
 * Decode the timestamp burned into the top strip of a video frame by
 * the API's robopipe_api/utils/timestamp_burnin.py. Constants must
 * match exactly.
 *
 * Layout (left-to-right, MSB first), 48 bits total:
 *   magic(8) | ts_lo32(32) | crc8(8)
 * Block size = max(MIN_BLOCK, frameWidth // (TOTAL_BITS * 5)).
 */

const MAGIC = 0xa5;
export const TOTAL_BITS = 48; // 8 + 32 + 8
const MIN_BLOCK = 4;

export function pickBlockSize(width: number): number {
  return Math.max(MIN_BLOCK, Math.floor(width / (TOTAL_BITS * 5)));
}

export function stripDimensions(frameWidth: number): {
  block: number;
  stripWidth: number;
  stripHeight: number;
} {
  const block = pickBlockSize(frameWidth);
  return { block, stripWidth: block * TOTAL_BITS, stripHeight: block };
}

function crc8(magic: number, ts: number): number {
  // Process 5 bytes MSB-first: magic, then ts bytes (3..0). Matches
  // the Python _crc8(framing, 5) where framing = (magic << 32) | ts.
  const bytes = [
    magic & 0xff,
    (ts >>> 24) & 0xff,
    (ts >>> 16) & 0xff,
    (ts >>> 8) & 0xff,
    ts & 0xff,
  ];
  let crc = 0;
  for (const byte of bytes) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) {
      crc = crc & 0x80 ? ((crc << 1) ^ 0x07) & 0xff : (crc << 1) & 0xff;
    }
  }
  return crc;
}

/**
 * Decode the burned-in timestamp from a frame's top strip.
 * `imageData` must cover at least the strip area (block rows ×
 * block * TOTAL_BITS cols) starting at frame origin (0, 0). `frameWidth`
 * is the native video frame width — used to pick the block size, NOT
 * `imageData.width` which may equal stripWidth.
 *
 * Returns the lower-32 bits of ts_us, or null on magic / CRC mismatch.
 */
export function decodeTimestampBurnin(
  imageData: ImageData,
  frameWidth: number,
): number | null {
  const { block, stripWidth, stripHeight } = stripDimensions(frameWidth);
  if (imageData.width < stripWidth || imageData.height < stripHeight) {
    return null;
  }

  const data = imageData.data;
  const rowStride = imageData.width * 4;

  // Sample the mean of the red channel across each block; threshold at 128.
  // Decoding uses `payload = 2*payload + bit` (instead of <<) so we stay
  // within Number's safe integer range (48 bits ≪ 2^53).
  let payload = 0;
  for (let i = 0; i < TOTAL_BITS; i++) {
    const x0 = i * block;
    let sum = 0;
    let count = 0;
    for (let y = 0; y < block; y++) {
      const rowOffset = y * rowStride;
      for (let x = x0; x < x0 + block; x++) {
        sum += data[rowOffset + x * 4];
        count++;
      }
    }
    const bit = sum / count >= 128 ? 1 : 0;
    payload = payload * 2 + bit;
  }

  // Split payload back into magic | ts | crc.
  const crc = payload % 256;
  const tsAndMagic = Math.floor(payload / 256); // 40 bits
  const ts = tsAndMagic % 0x100000000; // 32 bits
  const magic = Math.floor(tsAndMagic / 0x100000000); // 8 bits

  if (magic !== MAGIC) return null;
  if (crc8(magic, ts) !== crc) return null;
  return ts;
}
