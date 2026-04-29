import os
import tempfile
import time

import depthai as dai
from fastapi import UploadFile, WebSocket, status

from robopipe_api.dashboard.dashboard_handler import handle_detections

from ..common import (
    CameraDep,
    Mxid,
    NNConfigDep,
    SensorDep,
    StreamName,
    WSRelayDep,
)
from ...utils.detections_parser import parse_detections
from ...ws_relay import ProducerSkipMessage, ProducerTerminated
from . import stream_router


def _load_model_blob_from_bytes(
    model_bytes: bytes, filename: str
) -> "dai.OpenVINO.Blob | dai.NNArchive":
    """Load a model blob from raw bytes, handling both .blob and .tar.xz/.tar.gz formats."""
    if filename.endswith(".tar.xz") or filename.endswith(".tar.gz"):
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=filename[filename.rfind(".tar") :]
        ) as tmp:
            tmp.write(model_bytes)
            tmp_path = tmp.name
        try:
            return dai.NNArchive(tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        return dai.OpenVINO.Blob(list(model_bytes))


def _load_model_blob_from_path(
    model_path: str,
) -> "dai.OpenVINO.Blob | dai.NNArchive":
    """Load a model blob from a file path on disk."""
    if model_path.endswith(".tar.xz") or model_path.endswith(".tar.gz"):
        return dai.NNArchive(model_path)
    else:
        with open(model_path, "rb") as f:
            return dai.OpenVINO.Blob(list(f.read()))


@stream_router.get("/nn", tags=["nn"])
def get_neural_network(sensor: SensorDep):
    return sensor.nn_config


@stream_router.post("/nn", status_code=status.HTTP_201_CREATED, tags=["nn"])
async def deploy_neural_network(
    camera: CameraDep,
    stream_name: StreamName,
    model: UploadFile,
    config: NNConfigDep,
    sensor: SensorDep,
):
    model_bytes = await model.read()
    filename = model.filename or ""
    blob = _load_model_blob_from_bytes(model_bytes, filename)

    sensor.nn_config = config
    camera.deploy_nn(stream_name, blob, config)


@stream_router.delete("/nn", status_code=status.HTTP_202_ACCEPTED, tags=["nn"])
async def delete_neural_network(camera: CameraDep, stream_name: StreamName):
    camera.delete_nn(stream_name)


@stream_router.websocket("/nn")
async def get_sensor_detections(
    ws: WebSocket,
    camera: CameraDep,
    mxid: Mxid,
    stream_name: StreamName,
    relay: WSRelayDep,
):
    await ws.accept()

    # Track of last broadcast time per producer closure for throttle_hz.
    last_send_t: list[float] = [0.0]

    def producer():
        # Terminate cleanly (no retry log spam) when the sensor or NN have
        # been torn down under us — typically a DELETE /nn arriving while
        # this WS is still connected.
        sensor = camera.sensors.get(stream_name)
        if sensor is None or sensor.nn_config is None:
            raise ProducerTerminated()
        nn_config = sensor.nn_config

        detections = sensor.get_nn_detections()
        seq = detections.getSequenceNum()
        parsed_detections = parse_detections(
            detections, mask_max_dim=nn_config.mask_max_dim
        )
        # handle_detections() runs every tick: it updates zone tracking,
        # threshold accumulators and the events store. Throttling skips
        # only the network broadcast, not the evaluation.
        result = handle_detections(
            sensor.dashboard_config, parsed_detections, sensor.dashboard_run_session_id
        )
        result["seq"] = seq

        throttle_hz = nn_config.throttle_hz
        if throttle_hz and throttle_hz > 0:
            min_interval = 1.0 / throttle_hz
            now = time.monotonic()
            # Always emit frames carrying just-fired violations so QC
            # alerts aren't delayed by the throttle.
            has_violation_event = bool(result.get("violation_event_ids"))
            if not has_violation_event and now - last_send_t[0] < min_interval:
                raise ProducerSkipMessage()
            last_send_t[0] = now

        return result

    await relay.subscribe(key=(mxid, stream_name, "nn"), ws=ws, producer=producer)
