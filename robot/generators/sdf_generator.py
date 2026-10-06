from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _hex_to_sdf_color(value: str) -> str:
    color = str(value or '#ffffff').strip()
    if color.startswith('#'):
        hex_value = color[1:]
        if len(hex_value) == 3:
            hex_value = ''.join(ch * 2 for ch in hex_value)
        if len(hex_value) == 6:
            try:
                red = int(hex_value[0:2], 16) / 255.0
                green = int(hex_value[2:4], 16) / 255.0
                blue = int(hex_value[4:6], 16) / 255.0
                return f'{red:.6f} {green:.6f} {blue:.6f} 1.0'
            except ValueError:
                pass
    match = re.search(r'([0-9]*\.?[0-9]+)\s+([0-9]*\.?[0-9]+)\s+([0-9]*\.?[0-9]+)', color)
    if match:
        return f'{match.group(1)} {match.group(2)} {match.group(3)} 1.0'
    return '1.0 1.0 1.0 1.0'


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


def _resolve_asset_reference(robot_data: dict[str, Any], value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    asset_for_value = None
    for asset in robot_data.get("assets", []) or []:
        if not isinstance(asset, dict):
            continue
        if value in {str(asset.get("id") or ""), str(asset.get("name") or ""), str(asset.get("filename") or ""), str(asset.get("path") or ""), str(asset.get("uri") or "")}:
            asset_for_value = asset
            break
        base = str(asset.get("path") or asset.get("filename") or "").split('/')[-1].split('\\')[-1]
        if base == value.split('/')[-1].split('\\')[-1]:
            asset_for_value = asset
            break
    if asset_for_value is None:
        return value
    for key in ("path", "uri", "filename"):
        candidate = asset_for_value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return value


def _mesh_uri(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith('http://') or candidate.startswith('https://') or candidate.startswith('file://'):
        return candidate
    if not candidate:
        return candidate
    try:
        return Path(candidate).expanduser().resolve().as_uri()
    except Exception:
        return candidate


def _geom_block(component: dict[str, Any], robot_data: dict[str, Any] | None = None) -> str:
    geometry = str((component.get("visual") or {}).get("geometry") or component.get("geometry") or "box").lower()
    mesh_value = component.get("mesh")
    visual_mesh = (component.get("visual") or {}).get("mesh")
    mesh_ref = None
    for candidate in (component.get("asset_id"), mesh_value, visual_mesh):
        if isinstance(candidate, str):
            mesh_ref = _resolve_asset_reference(robot_data or {}, candidate)
            if mesh_ref:
                break
        elif isinstance(candidate, dict):
            mesh_ref = candidate.get("asset") or candidate.get("path") or candidate.get("uri") or candidate.get("filename")
            if isinstance(mesh_ref, str) and mesh_ref.strip():
                mesh_ref = _resolve_asset_reference(robot_data or {}, mesh_ref)
                break
    if mesh_ref:
        mesh_uri = _mesh_uri(str(mesh_ref))
        return (
            "      <geometry>\n"
            "        <mesh>\n"
            f"          <uri>{mesh_uri}</uri>\n"
            "        </mesh>\n"
            "      </geometry>\n"
        )
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
        material_color = _hex_to_sdf_color(color)
        model_lines.extend([
            f'    <link name="{component_id}">',
            f'      <pose>{pose}</pose>',
            f'      <visual name="{component_id}_visual">',
            '        <material>',
            f'          <ambient>{material_color}</ambient>',
            f'          <diffuse>{material_color}</diffuse>',
            f'          <specular>{material_color}</specular>',
            '        </material>',
            _geom_block(component, robot_data),
            '      </visual>',
            '      <inertial>',
            f'        <mass>{float(((component.get("physics") or {}).get("mass") or 0.0) if isinstance(component.get("physics"), dict) else 0.0):.6f}</mass>',
            f'        <inertia><ix>1.0</ix><iy>1.0</iy><iz>1.0</iz></inertia>',
            '      </inertial>',
            '    </link>',
        ])

    model_lines.append('  </model>')
    model_lines.append('</sdf>')
    return '\n'.join(model_lines)
