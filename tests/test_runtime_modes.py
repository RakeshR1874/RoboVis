from __future__ import annotations

from services.api.app.simulation_manager import SimulationManager


def test_default_runtime_mode_is_offline_preview() -> None:
    manager = SimulationManager()
    assert manager.mode == "OFFLINE_PREVIEW"
    assert manager.backend_name == "local_preview"
    assert manager.status_snapshot()["status"] == "OFFLINE_PREVIEW"


def test_ros_live_mode_does_not_require_gazebo() -> None:
    manager = SimulationManager()
    response = manager.set_mode("ROS_LIVE")
    assert response["mode"] == "ROS_LIVE"
    assert response["backend"] == "local_preview"
    assert manager.run({"components": []}) == {"status": "OFFLINE_PREVIEW", "details": "Offline preview; no Gazebo backend required."}


def test_simulation_mode_stays_optional() -> None:
    manager = SimulationManager()
    manager.set_mode("SIMULATION")
    snapshot = manager.status_snapshot()
    assert snapshot["status"] in {"IDLE", "OFFLINE_PREVIEW", "STOPPED", "ERROR"}
