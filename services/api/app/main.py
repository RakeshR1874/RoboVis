from __future__ import annotations

import asyncio
import json
import re
import shutil
import struct
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from robot.engineering.engine import compute_engineering_report
from robot.fixtures import create_robot_from_template, list_templates
from robot.generators.sdf_generator import generate_sdf
from robot.generators.urdf_generator import generate_urdf
from robot.validators.robot_validator import validate_robot_config
from services.api.app.ros_runtime import (
    build_foxglove_publish,
    map_joint_state_message,
    map_tf_message,
    normalize_topic_names,
    runtime_state_from_robot,
)
from services.api.app.simulation_manager import SIMULATION_MANAGER

ROOT_DIR = Path(__file__).resolve().parents[3]
ROS2_BIN = shutil.which("ros2") or str(Path("/opt/ros/jazzy/bin/ros2"))
STATE_PATH = ROOT_DIR / "services" / "api" / "data" / "robot_state.json"
ASSET_DIR = ROOT_DIR / "services" / "api" / "assets" / "uploads"
ASSET_INDEX_PATH = ROOT_DIR / "services" / "api" / "data" / "assets.json"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AUV Control Platform API")
app.mount("/assets", StaticFiles(directory=str(ASSET_DIR)), name="assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _read_saved_robot() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _persist_robot(robot: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(robot, indent=2), encoding="utf-8")


def _default_robot() -> dict[str, Any]:
    default_robot = create_robot_from_template("empty")
    _persist_robot(default_robot)
    return default_robot


def _load_assets() -> list[dict[str, Any]]:
    ASSET_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ASSET_INDEX_PATH.exists():
        return []
    try:
        payload = json.loads(ASSET_INDEX_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
    except json.JSONDecodeError:
        return []


def _persist_assets(assets: list[dict[str, Any]]) -> None:
    ASSET_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    ASSET_INDEX_PATH.write_text(json.dumps(assets, indent=2), encoding="utf-8")


def _safe_asset_name(filename: str) -> str:
    source = (filename or "upload.stl").strip()
    suffix = Path(source).suffix.lower()
    if suffix != ".stl":
        raise HTTPException(status_code=400, detail="Only .stl uploads are supported")
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(source).stem).strip("._") or "mesh"
    return f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def _looks_like_valid_stl(contents: bytes) -> bool:
    if len(contents) < 5:
        return False

    text = contents.decode("utf-8", errors="ignore").strip().lower()
    if text.startswith("solid "):
        required_tokens = ("facet normal", "outer loop", "vertex", "endfacet")
        return all(token in text for token in required_tokens)

    if len(contents) < 84:
        return False

    try:
        triangle_count = int.from_bytes(contents[80:84], byteorder="little", signed=False)
    except Exception:
        return False

    if triangle_count <= 0:
        return False

    return len(contents) >= 84 + triangle_count * 50


def _prune_invalid_assets() -> list[dict[str, Any]]:
    assets = _load_assets()
    kept: list[dict[str, Any]] = []
    for asset in assets:
        path_value = asset.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            continue
        path = Path(path_value)
        if not path.exists():
            continue
        try:
            contents = path.read_bytes()
        except OSError:
            continue
        if _looks_like_valid_stl(contents):
            kept.append(asset)
        else:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    _persist_assets(kept)
    return kept


def _load_robot() -> dict[str, Any]:
    robot = _read_saved_robot()
    if robot is not None:
        return robot
    return _default_robot()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/robot")
def get_robot() -> dict[str, Any]:
    return _load_robot()


@app.post("/api/robot/validate")
def validate_robot(robot: dict[str, Any]) -> dict[str, Any]:
    issues = validate_robot_config(robot)
    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


@app.get("/api/robot/engineering")
def get_robot_engineering() -> dict[str, Any]:
    robot = _load_robot()
    report = compute_engineering_report(robot)
    return {"report": report.to_dict()}


@app.get("/api/runtime/mode")
def get_runtime_mode() -> dict[str, Any]:
    return {"mode": SIMULATION_MANAGER.mode, "backend": SIMULATION_MANAGER.backend_name}


@app.post("/api/runtime/mode")
def set_runtime_mode(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode", "OFFLINE_PREVIEW")).upper()
    backend = payload.get("backend")
    return SIMULATION_MANAGER.set_mode(mode, str(backend) if backend else None)


@app.get("/api/robot/sdf")
def get_robot_sdf() -> dict[str, str]:
    return {"sdf": generate_sdf(_load_robot())}


@app.get("/api/robot/urdf")
def get_robot_urdf() -> dict[str, str]:
    return {"urdf": generate_urdf(_load_robot())}


@app.post("/api/robot/sdf")
def generate_robot_sdf(robot: dict[str, Any]) -> dict[str, str]:
    return {"sdf": generate_sdf(robot)}


@app.post("/api/robot/urdf")
def generate_robot_urdf(robot: dict[str, Any]) -> dict[str, str]:
    return {"urdf": generate_urdf(robot)}


@app.get("/api/robot/artifacts")
def get_robot_artifacts() -> dict[str, str]:
    robot = _load_robot()
    return {"sdf": generate_sdf(robot), "urdf": generate_urdf(robot)}


@app.post("/api/robot/artifacts")
def generate_robot_artifacts(robot: dict[str, Any]) -> dict[str, str]:
    return {"sdf": generate_sdf(robot), "urdf": generate_urdf(robot)}


@app.post("/api/assets/upload")
async def upload_asset(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.filename is None or not file.filename.strip():
        raise HTTPException(status_code=400, detail="Asset filename is required")

    safe_name = _safe_asset_name(file.filename)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    target_path = ASSET_DIR / safe_name
    contents = await file.read()
    if not contents or len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded STL file is empty")
    if not _looks_like_valid_stl(contents):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid STL mesh")

    target_path.write_bytes(contents)
    
    # Calculate mesh bounds
    bounds = _calculate_stl_bounds(target_path)
    
    asset = {
        "id": f"asset_{uuid.uuid4().hex[:12]}",
        "name": Path(safe_name).stem,
        "filename": safe_name,
        "path": str(target_path),
        "uri": f"http://127.0.0.1:8000/assets/{safe_name}",
        "type": "stl",
        "size": len(contents),
        "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    
    if bounds:
        asset["bounds"] = bounds
    
    assets = _prune_invalid_assets()
    assets.append(asset)
    _persist_assets(assets)
    return {"asset": asset}


@app.get("/api/assets")
def list_assets() -> dict[str, list[dict[str, Any]]]:
    return {"assets": _prune_invalid_assets()}


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, Any]:
    assets = _load_assets()
    for asset in assets:
        if str(asset.get("id")) == asset_id:
            return {"asset": asset}
    raise HTTPException(status_code=404, detail="Asset not found")


def _calculate_stl_bounds(file_path: Path) -> dict[str, Any] | None:
    """Calculate min/max bounds of STL mesh geometry."""
    try:
        contents = file_path.read_bytes()
    except (OSError, IOError):
        return None

    vertices: list[list[float]] = []

    # Try binary STL first (80-byte header + 4-byte triangle count + 50 bytes per triangle)
    if len(contents) >= 84:
        try:
            triangle_count = int.from_bytes(contents[80:84], byteorder="little", signed=False)
            expected_size = 84 + triangle_count * 50
            
            if 0 < triangle_count <= 1_000_000 and len(contents) >= expected_size:
                for i in range(triangle_count):
                    offset = 84 + i * 50 + 12  # Skip normal (3 floats = 12 bytes)
                    try:
                        # Read 3 vertices, each with 3 floats (x, y, z)
                        for v in range(3):
                            v_offset = offset + v * 12
                            x, y, z = struct.unpack('<fff', contents[v_offset:v_offset + 12])
                            vertices.append([x, y, z])
                    except struct.error:
                        break
                
                if vertices:
                    xs = [v[0] for v in vertices]
                    ys = [v[1] for v in vertices]
                    zs = [v[2] for v in vertices]
                    return {
                        "min": [min(xs), min(ys), min(zs)],
                        "max": [max(xs), max(ys), max(zs)],
                        "vertices": len(vertices),
                    }
        except (struct.error, ValueError, OverflowError):
            pass

    # Fallback: ASCII STL parsing
    try:
        text = contents.decode("utf-8", errors="ignore").lower()
        vertex_pattern = r"vertex\s+([+-]?[\d.eE]+)\s+([+-]?[\d.eE]+)\s+([+-]?[\d.eE]+)"
        matches = re.findall(vertex_pattern, text)
        for match in matches:
            try:
                vertices.append([float(match[0]), float(match[1]), float(match[2])])
            except ValueError:
                continue

        if vertices:
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            zs = [v[2] for v in vertices]
            return {
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
                "vertices": len(vertices),
            }
    except (UnicodeDecodeError, ValueError):
        pass

    return None


def _find_asset_references(robot: dict[str, Any], asset_id: str) -> list[str]:
    """Find all component IDs that reference a given asset."""
    references: list[str] = []
    components = robot.get("components", [])
    for comp in components:
        if comp.get("asset_id") == asset_id or comp.get("mesh", {}).get("asset") == asset_id:
            references.append(comp.get("id", "unknown"))
    return references


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str) -> dict[str, Any]:
    """Delete an asset, but only if no components reference it."""
    assets = _load_assets()
    asset_index = -1
    for idx, asset in enumerate(assets):
        if str(asset.get("id")) == asset_id:
            asset_index = idx
            break

    if asset_index == -1:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset = assets[asset_index]

    # Check if any components reference this asset
    robot = _read_saved_robot()
    if robot:
        references = _find_asset_references(robot, asset_id)
        if references:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete asset: referenced by components {references}. Unassign first.",
            )

    # Delete file if it exists
    path_value = asset.get("path")
    if path_value:
        try:
            Path(path_value).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass

    # Remove from index
    assets.pop(asset_index)
    _persist_assets(assets)

    return {"deleted": asset_id, "message": "Asset deleted successfully"}


@app.post("/api/robot/reset")
def reset_robot() -> dict[str, Any]:
    return _default_robot()


@app.get("/api/robot/templates")
def get_robot_templates() -> dict[str, Any]:
    return {"templates": list_templates()}


@app.post("/api/robot/from-template")
def create_robot_from_template_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    template = str(payload.get("template", "empty"))
    robot = create_robot_from_template(template)
    _persist_robot(robot)
    return robot


@app.put("/api/robot")
def save_robot(robot: dict[str, Any]) -> dict[str, Any]:
    issues = validate_robot_config(robot)
    if issues:
        raise HTTPException(status_code=400, detail={"issues": issues})

    _persist_robot(robot)
    return robot


@app.post("/api/simulation/run")
def run_simulation() -> dict[str, Any]:
    return SIMULATION_MANAGER.run(_load_robot())


@app.post("/api/simulation/stop")
def stop_simulation() -> dict[str, Any]:
    return SIMULATION_MANAGER.stop()


@app.post("/api/simulation/reset")
def reset_simulation() -> dict[str, Any]:
    return SIMULATION_MANAGER.reset()


@app.get("/api/simulation/status")
def get_simulation_status() -> dict[str, Any]:
    return SIMULATION_MANAGER.status_snapshot()


@app.get("/api/ros/discovery")
def get_ros_discovery() -> dict[str, Any]:
    try:
        topics_result = subprocess.run([ROS2_BIN, "topic", "list"], capture_output=True, text=True, check=False, timeout=5)
        nodes_result = subprocess.run([ROS2_BIN, "node", "list"], capture_output=True, text=True, check=False, timeout=5)
        services_result = subprocess.run([ROS2_BIN, "service", "list"], capture_output=True, text=True, check=False, timeout=5)
        params_result = subprocess.run([ROS2_BIN, "param", "list"], capture_output=True, text=True, check=False, timeout=5)
        topics = normalize_topic_names(topics_result.stdout.splitlines())
        nodes = normalize_topic_names(nodes_result.stdout.splitlines())
        services = normalize_topic_names(services_result.stdout.splitlines())
        parameters = normalize_topic_names(params_result.stdout.splitlines())
        return {"connected": len(topics) > 0 or len(nodes) > 0, "topics": topics, "nodes": nodes, "tf": [], "services": services, "parameters": parameters}
    except Exception:
        return {"connected": False, "topics": [], "nodes": [], "tf": [], "services": [], "parameters": []}


@app.post("/api/ros/command")
def send_ros_command(payload: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("topic") or "/auv/dev/cmd_vel")
    message = payload.get("message") or {"linear": {"x": 1.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.5}}
    msg_type = str(payload.get("type") or "geometry_msgs/msg/Twist")
    try:
        subprocess.run([ROS2_BIN, "topic", "pub", "--once", topic, msg_type, json.dumps(message)], check=False, capture_output=True, text=True, timeout=10)
        return {"accepted": True, "mode": SIMULATION_MANAGER.mode, "topic": topic, "type": msg_type, "details": "ROS command published."}
    except Exception as exc:
        return {"accepted": False, "mode": SIMULATION_MANAGER.mode, "details": f"Publish failed: {exc}"}


@app.websocket("/ws/projects/{project_id}/telemetry")
async def telemetry_socket(websocket: WebSocket, project_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            robot = _load_robot()
            report = compute_engineering_report(robot)
            try:
                ros_result = subprocess.run([ROS2_BIN, "topic", "list"], capture_output=True, text=True, check=False, timeout=5)
                ros_topics = [line.strip() for line in ros_result.stdout.splitlines() if line.strip()]
            except Exception:
                ros_topics = []
            try:
                gz_result = subprocess.run(["gz", "topic", "-l"], capture_output=True, text=True, check=False, timeout=5)
                gz_topics = [line.strip() for line in gz_result.stdout.splitlines() if line.strip()]
            except Exception:
                gz_topics = []
            payload = {
                "project_id": project_id,
                "status": SIMULATION_MANAGER.status_snapshot(),
                "telemetry": {
                    "position": [0.0, 0.0, 0.0],
                    "orientation": [0.0, 0.0, 0.0],
                    "linear_velocity": [0.0, 0.0, 0.0],
                    "angular_velocity": [0.0, 0.0, 0.0],
                    "depth": 0.0,
                    "imu": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
                    "thruster_state": {
                        "count": len([c for c in robot.get("components", []) if c.get("type") == "thruster"]),
                        "active": True,
                    },
                    "engineering": report.to_dict(),
                    "ros_topics": ros_topics[:10],
                    "gz_topics": gz_topics[:10],
                },
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception:
        return
