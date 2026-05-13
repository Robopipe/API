import json
import uuid
from pathlib import Path

import anyio.to_thread
from bs4 import BeautifulSoup
from fastapi import Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, Response

from robopipe_api.dashboard.config_store import config_store_factory
from robopipe_api.dashboard.dashboard_handler import (
    _threshold_tracker,
    apply_tuning_overrides,
    reset_zone_tracking,
)
from robopipe_api.dashboard.events_store import events_store_factory

from ...models.dashboard.dashboard_config import DashboardConfigUpdate
from ...models.dashboard.detection_event import DetectionEvent
from ...models.dashboard.user_settings import (
    TUNING_OVERRIDE_FIELDS,
    DashboardUserSettings,
)
from ...paths import get_data_dir
from ..common import (
    CameraDep,
    DashboardConfigsListDep,
    EventsStoreDep,
    Mxid,
    SensorDep,
    StreamName,
    SyncTaskDep,
    CameraManagerDep,
)
from . import JpegResponse, stream_router
from .nn import _load_model_blob_from_path


def _teardown_dashboard_run(sensor, events_store):
    if sensor.dashboard_run_session_id is not None:
        events_store.end_session(sensor.dashboard_run_session_id)
        sensor.dashboard_run_session_id = None
    if sensor.dashboard_config is not None:
        reset_zone_tracking(sensor.dashboard_config.id)
        _threshold_tracker.reset(sensor.dashboard_config.id)


@stream_router.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard(
    request: Request, mxid: Mxid, stream_name: StreamName, sensor: SensorDep
):
    if sensor.dashboard_config is None:
        return Response("No dashboard configured for this stream", status_code=404)

    dashboard_index = (
        Path(__file__).parent.parent.parent / "static" / "dashboard" / "index.html"
    )
    soup = BeautifulSoup(dashboard_index.read_text(), "html.parser")
    head = soup.head
    if head:
        store = config_store_factory()
        has_multiple = len(store.list_configs(mxid, stream_name)) > 1
        running_since = None
        if sensor.dashboard_run_session_id is not None:
            events_store = events_store_factory()
            running_since = events_store.get_session_start_time(
                sensor.dashboard_run_session_id
            )
        user_settings = store.load_user_settings(
            mxid, stream_name, sensor.dashboard_config.id
        )
        dashboard_config = {
            "configId": sensor.dashboard_config.id,
            "name": sensor.dashboard_config.name,
            "projectName": sensor.dashboard_config.projectName,
            "apiBase": str(request.url).removesuffix("/dashboard"),
            "mxid": mxid,
            "streamName": stream_name,
            "labels": [label.model_dump() for label in sensor.dashboard_config.labels],
            "testCases": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "severity": tc.severity,
                    "enabled": tc.enabled,
                    "thresholds": [t.model_dump() for t in tc.thresholds],
                }
                for tc in sensor.dashboard_config.testCases
            ],
            "zoneDirection": sensor.dashboard_config.zoneDirection,
            "zoneCenter": sensor.dashboard_config.zoneCenter,
            "zoneThickness": sensor.dashboard_config.zoneThickness,
            "optimistic": sensor.dashboard_config.optimistic,
            "thresholds": [t.model_dump() for t in sensor.dashboard_config.thresholds],
            "remoteBackendUrl": sensor.dashboard_config.remoteBackendUrl,
            "confidenceThreshold": sensor.dashboard_config.confidenceThreshold,
            "labelConfidenceThresholds": sensor.dashboard_config.labelConfidenceThresholds,
            "debounceFrames": sensor.dashboard_config.debounceFrames,
            "maxMissingFrames": sensor.dashboard_config.maxMissingFrames,
            "maxMatchDistance": sensor.dashboard_config.maxMatchDistance,
            "running": sensor.dashboard_run_session_id is not None,
            "runningSince": running_since,
            "hasMultipleConfigs": has_multiple,
            "userSettings": user_settings.model_dump(),
        }
        script_tag = soup.new_tag("script")
        script_tag.string = f"""
            window.DASHBOARD_CONFIG = {json.dumps(dashboard_config)};
        """
        head.append(script_tag)

    return HTMLResponse(content=str(soup))


@stream_router.post("/dashboard")
async def set_dashboard_config(
    camera: CameraDep,
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    configs: DashboardConfigsListDep,
    models: list[UploadFile],
):
    if len(configs) != len(models):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Number of configs ({len(configs)}) must match number of models ({len(models)})",
        )

    store = config_store_factory()
    store.clear_configs(mxid, stream_name)

    # Read all model files and store all configs
    for (dashboard_config, nn_config), model in zip(configs, models):
        model_bytes = await model.read()
        filename = model.filename or ""
        store.store_config(
            mxid, stream_name, dashboard_config, nn_config, model_bytes, filename
        )

    # Deploy the first config immediately
    first_config, first_nn_config = configs[0]
    first_stored = store.get_config(mxid, stream_name, first_config.id)
    blob = _load_model_blob_from_path(first_stored.model_path)

    sensor.nn_config = first_nn_config
    camera.deploy_nn(stream_name, blob, first_nn_config)
    sensor = camera.sensors.get(stream_name)  # Refresh after deploy
    sensor.dashboard_config = first_config
    # Apply persisted tuning overrides on top of the deployed config.
    user_settings = store.load_user_settings(mxid, stream_name, first_config.id)
    sensor._dashboard_config = apply_tuning_overrides(first_config, user_settings)

    return {
        "dashboard_url": f"/cameras/{mxid}/streams/{stream_name}/dashboard",
        "configs_count": len(configs),
    }


@stream_router.delete("/dashboard")
def delete_dashboard_config(
    camera: CameraDep,
    sensor: SensorDep,
    mxid: Mxid,
    stream_name: StreamName,
    events_store: EventsStoreDep,
    camera_manager: CameraManagerDep,
):
    _teardown_dashboard_run(sensor, events_store)
    sensor.dashboard_config = None
    config_store_factory().clear_configs(mxid, stream_name)
    camera.delete_nn(stream_name)
    camera_manager.restart_camera(mxid)


@stream_router.get("/dashboard/config")
def get_dashboard_config_params(sensor: SensorDep):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    return {
        "confidenceThreshold": sensor.dashboard_config.confidenceThreshold,
        "labelConfidenceThresholds": sensor.dashboard_config.labelConfidenceThresholds,
        "debounceFrames": sensor.dashboard_config.debounceFrames,
        "maxMissingFrames": sensor.dashboard_config.maxMissingFrames,
        "maxMatchDistance": sensor.dashboard_config.maxMatchDistance,
    }


@stream_router.patch("/dashboard/config")
def update_dashboard_config(
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    update: DashboardConfigUpdate,
):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )

    store = config_store_factory()
    config_id = sensor.dashboard_config.id

    settings = store.load_user_settings(mxid, stream_name, config_id)
    settings = settings.model_copy(update=update.model_dump(exclude_unset=True))
    store.save_user_settings(mxid, stream_name, config_id, settings)

    # Re-apply overlay onto the stored base so tuning changes don't compound.
    stored = store.get_config(mxid, stream_name, config_id)
    base = stored.dashboard_config if stored else sensor.dashboard_config
    updated = apply_tuning_overrides(base, settings)

    # Assign directly to bypass the property setter which resets
    # _dashboard_run_session_id and _active_config_id
    sensor._dashboard_config = updated

    return {
        "confidenceThreshold": updated.confidenceThreshold,
        "labelConfidenceThresholds": updated.labelConfidenceThresholds,
        "debounceFrames": updated.debounceFrames,
        "maxMissingFrames": updated.maxMissingFrames,
        "maxMatchDistance": updated.maxMatchDistance,
    }


@stream_router.get("/dashboard/user-settings")
def get_dashboard_user_settings(
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
) -> DashboardUserSettings:
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    return config_store_factory().load_user_settings(
        mxid, stream_name, sensor.dashboard_config.id
    )


@stream_router.put("/dashboard/user-settings")
def update_dashboard_user_settings(
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    settings: DashboardUserSettings,
) -> DashboardUserSettings:
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    store = config_store_factory()
    config_id = sensor.dashboard_config.id
    # Preserve tuning overrides — those are owned by PATCH /dashboard/config
    # and not part of this endpoint's request shape on the client.
    existing = store.load_user_settings(mxid, stream_name, config_id)
    preserved = {field: getattr(existing, field) for field in TUNING_OVERRIDE_FIELDS}
    merged = settings.model_copy(update=preserved)
    store.save_user_settings(mxid, stream_name, config_id, merged)
    return merged


@stream_router.get("/dashboard/configs")
def list_dashboard_configs(
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
):
    store = config_store_factory()
    configs = store.list_configs(mxid, stream_name)
    return {
        "active_config_id": sensor.active_config_id,
        "configs": [
            {
                "config_id": c.config_id,
                "config_name": c.config_name,
                "project_name": c.project_name,
            }
            for c in configs
        ],
    }


@stream_router.post("/dashboard/configs/{config_id}/activate")
def switch_dashboard_config(
    camera: CameraDep,
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    config_id: int,
    events_store: EventsStoreDep,
):
    store = config_store_factory()
    stored = store.get_config(mxid, stream_name, config_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    # Stop dashboard and reset evaluation state
    _teardown_dashboard_run(sensor, events_store)

    # Load model from disk and deploy
    blob = _load_model_blob_from_path(stored.model_path)
    sensor.nn_config = stored.nn_config
    camera.deploy_nn(stream_name, blob, stored.nn_config)

    # Refresh sensor reference after pipeline restart
    sensor = camera.sensors.get(stream_name)
    sensor.dashboard_config = stored.dashboard_config
    # Apply persisted tuning overrides on top of the activated config.
    user_settings = store.load_user_settings(mxid, stream_name, config_id)
    sensor._dashboard_config = apply_tuning_overrides(
        stored.dashboard_config, user_settings
    )

    return {"switched_to": config_id, "config_name": stored.config_name}


@stream_router.post("/dashboard/start")
def start_dashboard(sensor: SensorDep, events_store: EventsStoreDep):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    reset_zone_tracking(sensor.dashboard_config.id)
    sensor.dashboard_run_session_id = events_store.start_session(
        sensor.dashboard_config.id
    )
    return {"running": True}


@stream_router.post("/dashboard/stop")
def stop_dashboard(sensor: SensorDep, events_store: EventsStoreDep):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )
    events_store.end_session(sensor.dashboard_run_session_id)
    sensor.dashboard_run_session_id = None
    return {"running": False}


@stream_router.get("/dashboard/metrics")
def get_dashboard_metrics(sensor: SensorDep, events_store: EventsStoreDep):
    if sensor.dashboard_config is None or sensor.dashboard_run_session_id is None:
        return {}

    data = {}
    data["threshold_status"] = _threshold_tracker.get_status(
        sensor.dashboard_config.id, sensor.dashboard_config.testCases
    )
    data["master_threshold_status"] = _threshold_tracker.get_master_status(
        sensor.dashboard_config.id,
        sensor.dashboard_config.testCases,
        sensor.dashboard_config.thresholds,
    )
    data["counters"] = events_store.get_counters(sensor.dashboard_run_session_id)

    return data


@stream_router.post("/dashboard/events", status_code=status.HTTP_202_ACCEPTED)
async def cache_detection_events(
    events: list[DetectionEvent],
    mxid: Mxid,
    stream_name: StreamName,
    sensor: SensorDep,
    sync_task: SyncTaskDep,
):
    if (
        sensor.dashboard_config is None
        or sensor.dashboard_config.remoteBackendUrl is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No remote backend URL configured for this dashboard",
        )

    if sensor.dashboard_run_session_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dashboard is not running",
        )

    await anyio.to_thread.run_sync(
        lambda: events_store_factory().save_events(
            [e.model_dump() for e in events],
            mxid,
            stream_name,
            sensor.dashboard_config.remoteBackendUrl,
        )
    )
    sync_task.notify_new_events()


@stream_router.post("/dashboard/events/picture", status_code=status.HTTP_201_CREATED)
async def upload_event_picture(
    picture: UploadFile,
    event_ids: str = Form(...),
    sensor: SensorDep = None,
    events_store: EventsStoreDep = None,
):
    if sensor.dashboard_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No dashboard configured for this stream",
        )

    parsed_ids: list[int] = json.loads(event_ids)
    picture_bytes = await picture.read()

    pictures_dir = get_data_dir() / "event_pictures"
    pictures_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.jpg"
    file_path = pictures_dir / filename
    file_path.write_bytes(picture_bytes)

    picture_url = f"event_pictures/{filename}"
    events_store.update_event_picture(parsed_ids, picture_url)

    return {"picture_url": picture_url}


@stream_router.get(
    "/dashboard/events/{event_id}/picture",
    response_class=JpegResponse,
    responses={
        200: {
            "content": {
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}}
            },
            "description": "Violation picture in JPEG format",
        }
    },
)
def get_event_picture(event_id: int, events_store: EventsStoreDep):
    picture_url = events_store.get_event_picture_url(event_id)
    if picture_url is None:
        raise HTTPException(status_code=404, detail="Picture not found")

    file_path = get_data_dir() / picture_url
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Picture file not found")

    return JpegResponse(file_path.read_bytes())
