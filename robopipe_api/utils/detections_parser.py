import depthai as dai


def parse_detections(detections: dai.ImgDetections | dai.SpatialImgDetections):
    def parse_detection(detection: dai.ImgDetection | dai.SpatialImgDetection):
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coords": [detection.xmin, detection.ymin, detection.xmax, detection.ymax],
        }

        if isinstance(detection, dai.SpatialImgDetection):
            res["spatial_coords"] = {
                "x": detection.spatialCoordinates.x,
                "y": detection.spatialCoordinates.y,
                "z": detection.spatialCoordinates.z,
            }

        return res

    return list(map(parse_detection, detections.detections))
