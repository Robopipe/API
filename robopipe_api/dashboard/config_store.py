import json
import os
import shutil
from functools import lru_cache
from pathlib import Path

from ..models.dashboard.dashboard_config import DashboardConfig
from ..models.dashboard.stored_config import StoredConfigSummary, StoredDashboardConfig
from ..models.nn_config import NNConfig


class DashboardConfigStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or (
            Path(os.getenv("ROBOPIPE_DATA_DIR", str(Path.home() / ".robopipe")))
            / "models"
        )

    def _stream_dir(self, mxid: str, stream_name: str) -> Path:
        return self._base_dir / mxid / stream_name

    def store_config(
        self,
        mxid: str,
        stream_name: str,
        dashboard_config: DashboardConfig,
        nn_config: NNConfig,
        model_bytes: bytes,
        model_filename: str,
    ) -> StoredDashboardConfig:
        config_id = dashboard_config.id
        stream_dir = self._stream_dir(mxid, stream_name)
        stream_dir.mkdir(parents=True, exist_ok=True)

        # Determine file extension from original filename
        if model_filename.endswith(".tar.xz"):
            ext = ".tar.xz"
        elif model_filename.endswith(".tar.gz"):
            ext = ".tar.gz"
        else:
            ext = ".blob"

        model_path = stream_dir / f"{config_id}{ext}"
        model_path.write_bytes(model_bytes)

        # Save metadata as JSON sidecar
        metadata = {
            "dashboard_config": dashboard_config.model_dump(mode="json"),
            "nn_config": nn_config.model_dump(mode="json"),
            "model_filename": model_filename,
        }
        meta_path = stream_dir / f"{config_id}.json"
        meta_path.write_text(json.dumps(metadata, default=str))

        return StoredDashboardConfig(
            config_id=config_id,
            config_name=dashboard_config.name,
            dashboard_config=dashboard_config,
            nn_config=nn_config,
            model_path=str(model_path),
        )

    def list_configs(self, mxid: str, stream_name: str) -> list[StoredConfigSummary]:
        stream_dir = self._stream_dir(mxid, stream_name)
        if not stream_dir.exists():
            return []

        configs = []
        for meta_file in sorted(stream_dir.glob("*.json")):
            metadata = json.loads(meta_file.read_text())
            dc = metadata["dashboard_config"]
            configs.append(
                StoredConfigSummary(
                    config_id=dc["id"],
                    config_name=dc["name"],
                    project_name=dc.get("projectName", ""),
                )
            )
        return configs

    def get_config(
        self, mxid: str, stream_name: str, config_id: int
    ) -> StoredDashboardConfig | None:
        stream_dir = self._stream_dir(mxid, stream_name)
        meta_path = stream_dir / f"{config_id}.json"
        if not meta_path.exists():
            return None

        metadata = json.loads(meta_path.read_text())
        dashboard_config = DashboardConfig.model_validate(metadata["dashboard_config"])
        print(metadata["nn_config"])
        nn_config = NNConfig.model_validate(metadata["nn_config"])

        # Find the model file (could be .blob, .tar.xz, or .tar.gz)
        model_path = None
        for ext in [".blob", ".tar.xz", ".tar.gz"]:
            candidate = stream_dir / f"{config_id}{ext}"
            if candidate.exists():
                model_path = str(candidate)
                break

        if model_path is None:
            return None

        return StoredDashboardConfig(
            config_id=config_id,
            config_name=dashboard_config.name,
            dashboard_config=dashboard_config,
            nn_config=nn_config,
            model_path=model_path,
        )

    def clear_configs(self, mxid: str, stream_name: str) -> None:
        stream_dir = self._stream_dir(mxid, stream_name)
        if stream_dir.exists():
            shutil.rmtree(stream_dir)


@lru_cache(maxsize=1)
def config_store_factory() -> DashboardConfigStore:
    return DashboardConfigStore()
