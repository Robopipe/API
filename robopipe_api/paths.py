import os
from pathlib import Path


def get_data_dir() -> Path:
    return Path(os.getenv("ROBOPIPE_DATA_DIR", str(Path.home() / ".robopipe")))
