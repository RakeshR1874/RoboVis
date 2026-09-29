from __future__ import annotations

from typing import Any


def _robot_dict(robot: Any) -> dict[str, Any]:
    if isinstance(robot, dict):
        return robot
    if hasattr(robot, "model_dump"):
        return robot.model_dump(mode="json")
    raise TypeError("Robot configuration must be a dictionary or model instance.")


def _safe_vector(values: Any) -> tuple[float, float, float]:
    if not isinstance(values, (list, tuple)):
        return (0.0, 0.0, 0.0)
    normalized = [float(value) for value in values[:3]]
    if len(normalized) < 3:
        normalized.extend([0.0] * (3 - len(normalized)))
    return (normalized[0], normalized[1], normalized[2])


def _comp_position(component: dict[str, Any]) -> tuple[float, float, float]:
    transform = component.get("transform") or {}
    if isinstance(transform, dict):
        position = transform.get("position") or component.get("position")
        if position is not None:
            return _safe_vector(position)
    return _safe_vector(component.get("position", [0.0, 0.0, 0.0]))


def _geom_block(component: dict[str, Any]) -> str:
    geometry = str((component.get("visual") or {}).get("geometry") or component.get("geometry") or "box").lower()
    dims = component.get("dimensions")
    if not isinstance(dims, (list, tuple)):
        dims = [0.4, 0.2, 0.2]
    size = [float(dims[i]) if i < len(dims) else 0.0 for i in range(3)]
    if geometry == "cylinder":
        radius = max(float(size[0]) / 2.0, 0.05)
        length = max(float(size[2]) if len(size) > 2 else 0.4, 0.1)
        return (
            "      <geometry>\n"
            f"        <cylinder>\n"
            f"          <radius>{radius:.6f}</radius>\n"
            f"          <length>{length:.6f}</length>\n"
            "        </cylinder>\n"
            "      </geometry>\n"
        )
    if geometry == "sphere":
        radius = max(float(size[0]) / 2.0 if size[0] else 0.1, 0.05)
        return (
            "      <geometry>\n"
            f"        <sphere><radius>{radius:.6f}</radius></sphere>\n"
            "      </geometry>\n"
        )
    size_x = max(float(size[0]) if len(size) > 0 else 0.4, 0.1)
    size_y = max(float(size[1]) if len(size) > 1 else 0.2, 0.1)
    size_z = max(float(size[2]) if len(size) > 2 else 0.2, 0.1)
    return (
        "      <geometry>\n"
        f"        <box><size>{size_x:.6f} {size_y:.6f} {size_z:.6f}</size></box>\n"
        "      </geometry>\n"
    )


def generate_sdf(robot: Any) -> str:
    robot_data = _robot_dict(robot)
    name = str(robot_data.get("name", robot_data.get("id", "AUV")))
    components = robot_data.get("components", [])

    model_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sdf version="1.10">',
        f'  <model name="{name}">',
    ]

    for component in components:
        component_id = str(component.get("id", "component"))
        component_type = str(component.get("type", "generic"))
        position = _comp_position(component)
        pose = f"{position[0]:.6f} {position[1]:.6f} {position[2]:.6f} 0 0 0"
        color = ((component.get("visual") or {}).get("color") or component.get("color") or "#ffffff")
        model_lines.extend([
            f'    <link name="{component_id}">',
            f'      <pose>{pose}</pose>',
            f'      <visual name="{component_id}_visual">',
            '        <material>',
            f'          <ambient>{color}</ambient>',
            f'          <diffuse>{color}</diffuse>',
            '        </material>',
            _geom_block(component),
            '      </visual>',
            '      <inertial>',
            f'        <mass>{float(((component.get("physics") or {}).get("mass") or 0.0) if isinstance(component.get("physics"), dict) else 0.0):.6f}</mass>',
            f'        <inertia><ix>1.0</ix><iy>1.0</iy><iz>1.0</iz></inertia>',
            '      </inertial>',
            f'      <plugin name="{component_id}_{component_type}" filename="libgazebo_ros_control.so" />',
            '    </link>',
        ])

    model_lines.append('  </model>')
    model_lines.append('</sdf>')
    return '\n'.join(model_lines)
