import depthai as dai


def parse_detections(detections: dai.ImgDetections | dai.SpatialImgDetections):
    def parse_detection(detection: dai.ImgDetection | dai.SpatialImgDetection):
        res = {
            "label": detection.label,
            "confidence": detection.confidence,
            "coord": [detection.xmin, detection.ymin, detection.xmax, detection.ymax],
        }

        if isinstance(detection, dai.SpatialImgDetection):
            res["spatial_coordinates"] = {
                "x": detection.spatialCoordinates.x,
                "y": detection.spatialCoordinates.y,
                "z": detection.spatialCoordinates.z,
            }

        return res

    return list(map(parse_detection, detections.detections))
