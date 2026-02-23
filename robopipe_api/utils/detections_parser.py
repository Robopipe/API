import math

import depthai as dai
from depthai_nodes import Classifications, ImgDetectionsExtended, ImgDetectionExtended


def parse_detections(detections: dai.ImgDetections):
    def parse_detection(detection: dai.ImgDetection):
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coords": [detection.xmin, detection.ymin, detection.xmax, detection.ymax],
        }

        return res

    return {"detections": list(map(parse_detection, detections.detections))}


def parse_classifications(classifications: Classifications):
    pass


def parse_img_detections_extended(
    img_detections_extended: ImgDetectionsExtended,
):
    def parse_rect(rect: dai.RotatedRect) -> list[float]:
        cx, cy = rect.center.x, rect.center.y
        w, h = rect.size.width, rect.size.height
        angle_rad = math.radians(rect.angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Half dimensions
        hw, hh = w / 2, h / 2

        # Four corners of the rotated rectangle
        corners_x = [
            cx + dx * cos_a - dy * sin_a
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        ]
        corners_y = [
            cy + dx * sin_a + dy * cos_a
            for dx, dy in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        ]

        xmin = min(corners_x)
        ymin = min(corners_y)
        xmax = max(corners_x)
        ymax = max(corners_y)

        return [xmin, ymin, xmax, ymax]

    def parse_detection(detection: ImgDetectionExtended):
        rotated_rect = detection.rotated_rect
        coords = parse_rect(rotated_rect)
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coords": coords,
        }

        return res

    res = {
        "detections": list(map(parse_detection, img_detections_extended.detections)),
        "masks": img_detections_extended.masks.tolist(),
    }

    return res


def parse_detections(
    detections: dai.ImgDetections | Classifications | ImgDetectionsExtended,
):
    if isinstance(detections, dai.ImgDetections):
        return parse_detections(detections)
    elif isinstance(detections, Classifications):
        return parse_classifications(detections)
    elif isinstance(detections, ImgDetectionsExtended):
        return parse_img_detections_extended(detections)
    else:
        raise ValueError("Unsupported detections type")
