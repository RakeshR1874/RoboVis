from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from robot.engineering.engine import compute_engineering_report
from robot.fixtures.auv_001 import create_auv001_fixture
from robot.generators.sdf_generator import generate_sdf
from robot.validators.robot_validator import validate_robot_config

ROOT_DIR = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT_DIR / "services" / "api" / "data" / "robot_state.json"

app = FastAPI(title="AUV Control Platform API")
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
    default_robot = create_auv001_fixture()
    _persist_robot(default_robot)
    return default_robot


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


@app.get("/api/robot/sdf")
def get_robot_sdf() -> dict[str, str]:
    return {"sdf": generate_sdf(_load_robot())}


@app.post("/api/robot/sdf")
def generate_robot_sdf(robot: dict[str, Any]) -> dict[str, str]:
    return {"sdf": generate_sdf(robot)}


@app.post("/api/robot/reset")
def reset_robot() -> dict[str, Any]:
    return _default_robot()


@app.put("/api/robot")
def save_robot(robot: dict[str, Any]) -> dict[str, Any]:
    issues = validate_robot_config(robot)
    if issues:
        raise HTTPException(status_code=400, detail={"issues": issues})

    _persist_robot(robot)
    return robot
