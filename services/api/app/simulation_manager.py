from __future__ import annotations

import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import Any

from robot.generators.sdf_generator import generate_sdf
from robot.validators.robot_validator import validate_robot_config

ROOT_DIR = Path(__file__).resolve().parents[3]
SIM_DIR = ROOT_DIR / "simulation"
SDF_PATH = SIM_DIR / "generated" / "auv_robot.sdf"


class SimulationBackend:
    name = "base"

    def run(self, robot: dict[str, Any]) -> dict[str, Any]:
        return {"status": "OFFLINE_PREVIEW", "details": "Preview backend is active"}

    def stop(self) -> dict[str, Any]:
        return {"status": "STOPPED", "details": "Preview backend stopped"}

    def reset(self) -> dict[str, Any]:
        return {"status": "IDLE", "details": "Preview backend reset"}

    def status_snapshot(self) -> dict[str, Any]:
        return {"status": "OFFLINE_PREVIEW", "details": "Preview backend idle"}


class LocalPreviewBackend(SimulationBackend):
    name = "local_preview"

    def run(self, robot: dict[str, Any]) -> dict[str, Any]:
        return {"status": "OFFLINE_PREVIEW", "details": "Offline preview active; Gazebo is optional."}

    def stop(self) -> dict[str, Any]:
        return {"status": "STOPPED", "details": "Offline preview stopped"}

    def reset(self) -> dict[str, Any]:
        return {"status": "IDLE", "details": "Offline preview reset"}

    def status_snapshot(self) -> dict[str, Any]:
        return {"status": "OFFLINE_PREVIEW", "details": "Offline preview mode"}


class GazeboBackend(SimulationBackend):
    name = "gazebo"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._status = "IDLE"
        self._details = "Simulation is idle"
        self._stdout: list[str] = []
        self._stderr: list[str] = []
        self._log_thread: threading.Thread | None = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def details(self) -> str:
        return self._details

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process and self._process.poll() is None else None

    def _capture_output(self) -> None:
        if self._process is None or self._process.stdout is None:
            return
        try:
            for line in self._process.stdout:
                stripped = line.rstrip()
                if not stripped:
                    continue
                self._stdout.append(stripped)
                if len(self._stdout) > 200:
                    self._stdout.pop(0)
        except Exception:
            pass

    def _capture_stderr(self) -> None:
        if self._process is None or self._process.stderr is None:
            return
        try:
            for line in self._process.stderr:
                stripped = line.rstrip()
                if not stripped:
                    continue
                self._stderr.append(stripped)
                if len(self._stderr) > 200:
                    self._stderr.pop(0)
        except Exception:
            pass

    def reset(self) -> dict[str, Any]:
        with self._lock:
            self.stop()
            self._status = "IDLE"
            self._details = "Simulation reset"
            self._stdout.clear()
            self._stderr.clear()
            return {"status": self._status, "pid": self.pid, "details": self._details}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._status = "STOPPED"
                self._details = "Simulation already stopped"
                return {"status": self._status, "pid": None, "details": self._details}
            try:
                self._status = "STOPPING"
                self._details = "Stopping Gazebo"
                self._process.send_signal(signal.SIGINT)
                self._process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self._process.terminate()
                    self._process.wait(timeout=10)
                except Exception:
                    self._process.kill()
                    self._process.wait(timeout=10)
            finally:
                self._process = None
                self._status = "STOPPED"
                self._details = "Simulation stopped"
                return {"status": self._status, "pid": None, "details": self._details}

    def _write_sdf(self, robot: dict[str, Any]) -> str:
        SIM_DIR.mkdir(parents=True, exist_ok=True)
        sdf_text = generate_sdf(robot)
        SDF_PATH.parent.mkdir(parents=True, exist_ok=True)
        SDF_PATH.write_text(sdf_text, encoding="utf-8")
        return str(SDF_PATH)

    def run(self, robot: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            issues = validate_robot_config(robot)
            if issues:
                self._status = "ERROR"
                self._details = "; ".join(issues)
                return {"status": self._status, "details": self._details}

            self.stop()
            sdf_path = self._write_sdf(robot)
            self._status = "STARTING"
            self._details = f"Launching Gazebo with {sdf_path}"

            cmd = [
                "gz",
                "sim",
                "-v",
                "4",
                sdf_path,
            ]
            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(ROOT_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env={**os.environ, "RMW_IMPLEMENTATION": "rmw_cyclonedds_cpp"},
                )
                self._log_thread = threading.Thread(target=self._capture_output, daemon=True)
                self._log_thread.start()
                stderr_thread = threading.Thread(target=self._capture_stderr, daemon=True)
                stderr_thread.start()
                self._status = "RUNNING"
                self._details = f"Gazebo launched: {sdf_path}"
                return {"status": self._status, "pid": self.pid, "details": self._details}
            except Exception as exc:  # pragma: no cover - env-dependent runtime path
                self._status = "ERROR"
                self._details = f"Gazebo launch failed: {exc}"
                self._process = None
                return {"status": self._status, "details": self._details}

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is not None:
                self._status = "STOPPED"
                self._details = "Gazebo process exited"
                self._process = None
            return {"status": self._status, "pid": self.pid, "details": self._details}


class SimulationManager:
    def __init__(self) -> None:
        self._backend: SimulationBackend = LocalPreviewBackend()
        self._mode = "OFFLINE_PREVIEW"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def set_mode(self, mode: str, backend_name: str | None = None) -> dict[str, Any]:
        if mode == "SIMULATION":
            if backend_name in {"gazebo", None}:
                self._backend = GazeboBackend()
                self._mode = "SIMULATION"
                return {"mode": self._mode, "backend": self._backend.name, "status": "ready"}
            self._backend = LocalPreviewBackend()
            self._mode = "OFFLINE_PREVIEW"
            return {"mode": self._mode, "backend": self._backend.name, "status": "fallback_preview"}

        if mode == "ROS_LIVE":
            self._backend = LocalPreviewBackend()
            self._mode = "ROS_LIVE"
            return {"mode": self._mode, "backend": self._backend.name, "status": "ros_live"}

        self._backend = LocalPreviewBackend()
        self._mode = "OFFLINE_PREVIEW"
        return {"mode": self._mode, "backend": self._backend.name, "status": "offline"}

    def run(self, robot: dict[str, Any]) -> dict[str, Any]:
        if self._mode == "SIMULATION":
            return self._backend.run(robot)
        return {"status": "OFFLINE_PREVIEW", "details": "Offline preview; no Gazebo backend required."}

    def stop(self) -> dict[str, Any]:
        if self._mode == "SIMULATION":
            return self._backend.stop()
        return {"status": "STOPPED", "details": "Preview mode is not running a simulation backend."}

    def reset(self) -> dict[str, Any]:
        if self._mode == "SIMULATION":
            return self._backend.reset()
        self._mode = "OFFLINE_PREVIEW"
        return {"status": "IDLE", "details": "Preview mode reset to OFFLINE_PREVIEW"}

    def status_snapshot(self) -> dict[str, Any]:
        if self._mode == "SIMULATION":
            return self._backend.status_snapshot()
        return {"status": "OFFLINE_PREVIEW", "details": "Gazebo is optional; preview is active."}


SIMULATION_MANAGER = SimulationManager()
SIMULATION_MANAGER.set_mode("OFFLINE_PREVIEW")
