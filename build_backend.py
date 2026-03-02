"""
Custom build backend that wraps setuptools to build the dashboard_web
frontend (npm run build) before creating the Python package.
"""

import os
import subprocess
import sys

from setuptools.build_meta import *  # noqa: F401, F403
from setuptools.build_meta import (
    build_sdist as _build_sdist,
    build_wheel as _build_wheel,
)

_DASHBOARD_DIR = "dashboard_web"


def _build_dashboard() -> None:
    """Run npm install + npm run build inside dashboard_web/."""
    root = os.path.dirname(os.path.abspath(__file__))
    dashboard_path = os.path.join(root, _DASHBOARD_DIR)

    if not os.path.isdir(dashboard_path):
        print(f"[build_backend] {_DASHBOARD_DIR}/ not found – skipping dashboard build")
        return

    print(f"[build_backend] Installing dashboard_web dependencies …")
    subprocess.check_call(["npm", "install"], cwd=dashboard_path)

    print(f"[build_backend] Building dashboard_web …")
    subprocess.check_call(["npm", "run", "build"], cwd=dashboard_path)

    print("[build_backend] Dashboard build complete.")


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _build_dashboard()
    return _build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _build_dashboard()
    return _build_sdist(sdist_directory, config_settings)
