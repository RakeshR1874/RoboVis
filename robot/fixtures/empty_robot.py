from __future__ import annotations

from robot.schemas.robot_config import RobotConfig


def create_empty_robot() -> dict:
    """Create an empty robot with no components."""
    robot = RobotConfig(
        id="robot_default",
        name="My Robot",
        physical={
            "mass": 1.0,
            "volume": 0.001,
            "density": 1000.0,
            "dimensions": {"length": 0.5, "width": 0.3, "height": 0.3},
            "inertia": {"ix": 0.01, "iy": 0.01, "iz": 0.01},
        },
        buoyancy={
            "enabled": False,
            "fluid_density": 1000.0,
            "displacement_volume": 0.001,
        },
        controller={
            "type": "none",
            "parameters": {},
        },
        components=[],
    )
    return robot.model_dump(by_alias=False)
