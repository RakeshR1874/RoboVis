from __future__ import annotations

from typing import Any

from robot.assembly import validate_component_model


def _vector_magnitude(values: Any) -> float:
    if not isinstance(values, (list, tuple)):
        return 0.0
    try:
        numbers = [float(value) for value in values]
    except (TypeError, ValueError):
        return 0.0
    if len(numbers) != 3:
        return 0.0
    return (numbers[0] ** 2 + numbers[1] ** 2 + numbers[2] ** 2) ** 0.5


def validate_robot_config(robot: Any) -> list[str]:
    if not isinstance(robot, dict):
        return ["Robot configuration must be an object."]

    issues: list[str] = []
    components = robot.get("components", [])
    physical = robot.get("physical", {})
    buoyancy = robot.get("buoyancy", {})

    if not isinstance(components, list) or not components:
        issues.append("Robot must include at least one component.")

    seen_ids: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            issues.append("Each component must be an object.")
            continue

        component_id = component.get("id")
        if not component_id:
            issues.append("Each component must include an id.")
            continue
        if component_id in seen_ids:
            issues.append(f"Duplicate component id: {component_id}")
        seen_ids.add(component_id)

        if component.get("type") == "thruster":
            direction = component.get("properties", {}).get("thrust_axis") or component.get("direction", [0.0, 0.0, 0.0])
            magnitude = _vector_magnitude(direction)
            if magnitude <= 0:
                issues.append(f"Thruster {component_id} direction must be non-zero.")

            max_force = component.get("properties", {}).get("max_force")
            if max_force is None:
                max_force = component.get("max_force")
            if max_force is None or float(max_force) < 0:
                issues.append(f"Thruster {component_id} max_force must be a non-negative number.")

    issues.extend(validate_component_model(robot))

    mass = physical.get("mass")
    try:
        if mass is None or float(mass) <= 0:
            issues.append("Physical mass must be greater than 0.")
    except (TypeError, ValueError):
        issues.append("Physical mass must be a valid number.")

    volume = physical.get("volume")
    try:
        if volume is None or float(volume) <= 0:
            issues.append("Physical volume must be greater than 0.")
    except (TypeError, ValueError):
        issues.append("Physical volume must be a valid number.")

    density = physical.get("density")
    try:
        if density is None or float(density) <= 0:
            issues.append("Physical density must be greater than 0.")
    except (TypeError, ValueError):
        issues.append("Physical density must be a valid number.")

    if buoyancy.get("enabled") is True:
        fluid_density = buoyancy.get("fluid_density")
        try:
            if fluid_density is None or float(fluid_density) <= 0:
                issues.append("Buoyancy fluid density must be greater than 0.")
        except (TypeError, ValueError):
            issues.append("Buoyancy fluid density must be a valid number.")

    return issues
