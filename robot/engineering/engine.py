from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

GRAVITY = 9.81


@dataclass(frozen=True)
class ConfiguredEngineering:
    mass: float
    volume: float
    density: float
    fluid_density: float
    displacement_volume: float


@dataclass(frozen=True)
class CalculatedEngineering:
    weight: float
    buoyancy: float
    net_vertical_force: float


@dataclass(frozen=True)
class ThrusterForce:
    component_id: str
    name: str
    max_force: float
    force: float
    direction: tuple[float, float, float]


@dataclass(frozen=True)
class EngineeringReport:
    configured: ConfiguredEngineering
    calculated: CalculatedEngineering
    buoyancy_status: str
    warnings: list[str] = field(default_factory=list)
    thruster_forces: list[ThrusterForce] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["thruster_forces"] = [
            {
                "component_id": item.component_id,
                "name": item.name,
                "max_force": item.max_force,
                "force": item.force,
                "direction": list(item.direction),
            }
            for item in self.thruster_forces
        ]
        return payload


def _as_dict(robot: Any) -> dict[str, Any]:
    if isinstance(robot, dict):
        return robot
    if hasattr(robot, "model_dump"):
        return robot.model_dump(mode="json")
    raise TypeError("Robot configuration must be a dictionary or model instance.")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _component_thrust_axis(component: dict[str, Any]) -> tuple[float, float, float]:
    props = component.get("properties") or {}
    thrust_axis = props.get("thrust_axis") or component.get("direction") or [1.0, 0.0, 0.0]
    if not isinstance(thrust_axis, (list, tuple)):
        return (1.0, 0.0, 0.0)
    values = list(thrust_axis)[:3]
    if len(values) < 3:
        values.extend([0.0] * (3 - len(values)))
    return tuple(float(value) for value in values)


def compute_engineering_report(robot: Any) -> EngineeringReport:
    robot_data = _as_dict(robot)
    physical = robot_data.get("physical", {})
    buoyancy = robot_data.get("buoyancy", {})
    components = robot_data.get("components", [])

    mass = _safe_float(physical.get("mass"), 0.0)
    volume = _safe_float(physical.get("volume"), 0.0)
    density = _safe_float(physical.get("density"), 0.0)
    fluid_density = _safe_float(buoyancy.get("fluid_density"), 0.0)
    displacement_volume = _safe_float(buoyancy.get("displacement_volume"), 0.0)

    warnings: list[str] = []
    if mass < 0:
        warnings.append("Negative mass detected; check physical mass settings.")
    if volume < 0:
        warnings.append("Invalid volume; volume must be non-negative.")
    if density < 0:
        warnings.append("Negative density detected; check the material definition.")
    if fluid_density < 0:
        warnings.append("Invalid fluid density; fluid density must be non-negative.")

    weight = max(mass, 0.0) * GRAVITY
    buoyancy_force = max(fluid_density, 0.0) * max(volume, 0.0) * GRAVITY
    net_vertical_force = buoyancy_force - weight

    if net_vertical_force > 0:
        status = "FLOATING"
    elif net_vertical_force < 0:
        status = "SINKING"
    else:
        status = "NEUTRAL"

    thruster_forces: list[ThrusterForce] = []
    for component in components:
        if component.get("type") != "thruster":
            continue
        props = component.get("properties") or {}
        max_force = _safe_float(props.get("max_force", component.get("max_force", 0.0)), 0.0)
        thruster_forces.append(
            ThrusterForce(
                component_id=str(component.get("id", "thruster")),
                name=str(component.get("name", "Thruster")),
                max_force=max_force,
                force=max(max_force, 0.0),
                direction=_component_thrust_axis(component),
            )
        )

    return EngineeringReport(
        configured=ConfiguredEngineering(
            mass=mass,
            volume=volume,
            density=density,
            fluid_density=fluid_density,
            displacement_volume=displacement_volume,
        ),
        calculated=CalculatedEngineering(
            weight=round(weight, 2),
            buoyancy=round(buoyancy_force, 2),
            net_vertical_force=round(net_vertical_force, 2),
        ),
        buoyancy_status=status,
        warnings=warnings,
        thruster_forces=thruster_forces,
    )
