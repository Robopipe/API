# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Robopipe API is an edge-based machine vision platform for industrial automation. It connects Luxonis OAK cameras (via DepthAI SDK) with UniPi PLCs, runs AI inference on-device, and streams results to a React dashboard.

## Commands

### Backend

```bash
# Run the API
python3 -m robopipe_api
# or
robopipe-api

# Custom env file
ROBOPIPE_API_ENV=/path/to/.env python3 -m robopipe_api

# Build Python wheel (auto-builds frontend first via build_backend.py)
pip install build && python -m build --wheel
```

### Frontend (`dashboard_web/`)

```bash
npm install
npm run dev      # Dev server
npm run build    # Compile to dist/ (copied to robopipe_api/static/)
npm run lint     # ESLint
```

### No automated tests exist in this repo.

## Architecture

### Entry Point

`robopipe_api/robopipe.py` — FastAPI app with a lifespan manager that boots cameras, initializes streaming, WebRTC, and optionally loads the controller config. Three routers:
- `/cameras` — camera listing, boot/shutdown, stats, IR
- `/cameras/{mxid}/streams` — WebRTC, WebSocket relay, sensor config
- `/controller/*` — dynamic PLC device endpoints (digital/analog I/O, Modbus registers)

### Camera System (`robopipe_api/camera/`)

Wraps DepthAI SDK. Each camera runs one of several pipelines:
- `EmptyPipeline`, `StreamingPipeline`, `DepthPipeline`, `NNPipeline`

Sensors (RGB, stereo, depth) are individually configurable and can be activated/deactivated at runtime.

### Streaming

- **WebRTC** (`robopipe_api/webrtc_manager.py`, `robopipe_api/video_encoder.py`) — aiortc-based low-latency video
- **WebSocket Relay** (`robopipe_api/ws_relay.py`) — generic producer/consumer broadcast to multiple clients; lazily creates producer tasks
- Detection results are parsed in `robopipe_api/utils/detections_parser.py` and sent over WebSocket alongside video frames

### Dashboard

- **Backend** (`robopipe_api/dashboard/dashboard_handler.py`) — filters detections by region constraints, line crossing, area, aspect ratio, and confidence
- **Frontend** (`dashboard_web/`) — React 19 + Vite + Tailwind CSS; renders video + detection overlays from WebSocket stream
- The compiled frontend is bundled into the Python package under `robopipe_api/static/`

### Controller System (`robopipe_api/controller/`)

Configuration-driven UniPi PLC integration over 1-Wire, TCP, Serial, and Modbus. Loaded via `CONTROLLER_CONFIG` env var pointing to a config directory.

### Models (`robopipe_api/models/`)

Pydantic v2 models for detections (bounding box, segmentation), sensors, streams, and dashboard config.

## Environment Variables

See `.env.example`:
```
HOST=0.0.0.0
PORT=8080
CORS_ORIGINS=*
CONTROLLER_CONFIG=/path/to/robopipe/config/dir
```

## Key Dependencies

- `depthai` — Luxonis OAK camera SDK (hardware interface)
- `aiortc` — WebRTC implementation
- `fastapi` + `uvicorn` — API server
- `pymodbus` — Modbus protocol for PLCs
- `asyncowfs` — async 1-Wire filesystem (git dependency)
