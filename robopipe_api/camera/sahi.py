from __future__ import annotations

from dataclasses import dataclass

from ..models.detection.bbox_detection import BBoxDetection, BBoxDetections
from ..models.sahi_config import SAHIConfig


@dataclass(frozen=True)
class Tile:
    x1: float
    y1: float
    x2: float
    y2: float


def bbox_area(coords: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = coords
    return max(0, x2 - x1) * max(0, y2 - y1)


def bbox_iou(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    inter_x1 = max(a[0], b[0])
    inter_y1 = max(a[1], b[1])
    inter_x2 = min(a[2], b[2])
    inter_y2 = min(a[3], b[3])
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)

    area_a = bbox_area(a)
    area_b = bbox_area(b)
    union = area_a + area_b - inter_area

    if union <= 0:
        return 0.0
    return inter_area / union


def compute_tiles(config: SAHIConfig) -> list[Tile]:
    stride_x = config.slice_width * (1 - config.overlap_ratio)
    stride_y = config.slice_height * (1 - config.overlap_ratio)

    tiles: list[Tile] = []
    y = 0.0
    while y < 1.0:
        x = 0.0
        while x < 1.0:
            tiles.append(
                Tile(
                    x1=x,
                    y1=y,
                    x2=min(x + config.slice_width, 1.0),
                    y2=min(y + config.slice_height, 1.0),
                )
            )
            x += stride_x
        y += stride_y

    return tiles


def remap_tile_detections(detections: BBoxDetections, tile: Tile) -> list[BBoxDetection]:
    tile_w = tile.x2 - tile.x1
    tile_h = tile.y2 - tile.y1
    remapped: list[BBoxDetection] = []

    for det in detections.detections:
        xmin, ymin, xmax, ymax = det.coords
        remapped.append(
            BBoxDetection(
                label=det.label,
                confidence=det.confidence,
                coords=(
                    tile.x1 + xmin * tile_w,
                    tile.y1 + ymin * tile_h,
                    tile.x1 + xmax * tile_w,
                    tile.y1 + ymax * tile_h,
                ),
            )
        )

    return remapped


def nms_merge(
    all_detections: list[BBoxDetection],
    iou_threshold: float,
) -> list[BBoxDetection]:
    if not all_detections:
        return []

    # Group by label for per-class NMS
    by_label: dict[int, list[BBoxDetection]] = {}
    for det in all_detections:
        by_label.setdefault(det.label, []).append(det)

    result: list[BBoxDetection] = []

    for dets in by_label.values():
        # Sort by confidence descending
        dets.sort(key=lambda d: d.confidence, reverse=True)
        keep: list[BBoxDetection] = []

        for det in dets:
            suppressed = False
            for kept in keep:
                if bbox_iou(det.coords, kept.coords) > iou_threshold:
                    suppressed = True
                    break
            if not suppressed:
                keep.append(det)

        result.extend(keep)

    return result
