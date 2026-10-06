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


def _asset_lookup(robot_data: dict[str, Any]) -> dict[str, Any]:
    lookup: dict[str, Any] = {}
    for asset in robot_data.get("assets", []) or []:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id") or asset.get("name") or "asset")
        lookup[asset_id] = asset
        name = str(asset.get("name") or "")
        if name:
            lookup[name] = asset
        for key in (asset.get("path"), asset.get("uri"), asset.get("filename")):
            if isinstance(key, str):
                lookup[key] = asset
                lookup[key.split('/')[-1].split('\\')[-1]] = asset
    return lookup


def _resolve_mesh_path(robot_data: dict[str, Any], value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    asset_lookup = _asset_lookup(robot_data)
    if value in asset_lookup:
        asset = asset_lookup[value]
        for key in ("path", "uri", "filename"):
            candidate = asset.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    basename = value.split('/')[-1].split('\\')[-1]
    if basename in asset_lookup:
        asset = asset_lookup[basename]
        for key in ("path", "uri", "filename"):
            candidate = asset.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return value


def _extract_mesh_path(component: dict[str, Any], robot_data: dict[str, Any] | None = None) -> str | None:
    visual = component.get("visual") if isinstance(component.get("visual"), dict) else {}
    mesh_value = component.get("mesh")
    candidates = [
        component.get("asset_id"),
        mesh_value,
        visual.get("mesh"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            resolved = _resolve_mesh_path(robot_data, candidate) if robot_data is not None else candidate
            if resolved:
                return resolved
        elif isinstance(candidate, dict):
            value = candidate.get("asset") or candidate.get("path") or candidate.get("uri") or candidate.get("filename")
            resolved = _resolve_mesh_path(robot_data, value) if robot_data is not None and isinstance(value, str) else value
            if isinstance(resolved, str) and resolved.strip():
                return resolved
    return None


def _link_geometry(component: dict[str, Any], robot_data: dict[str, Any] | None = None) -> str:
    visual = component.get("visual") if isinstance(component.get("visual"), dict) else {}
    geometry = str((visual.get("geometry") or component.get("geometry") or "box")).lower()
    mesh_path = _extract_mesh_path(component, robot_data)
    if mesh_path:
        return (
            "      <visual>\n"
            "        <geometry>\n"
            f"          <mesh filename=\"{mesh_path}\" />\n"
            "        </geometry>\n"
            "      </visual>\n"
        )

    if geometry == "cylinder":
        radius = 0.1
        length = 0.4
        return (
            "      <visual>\n"
            "        <geometry>\n"
            f"          <cylinder radius=\"{radius}\" length=\"{length}\" />\n"
            "        </geometry>\n"
            "      </visual>\n"
        )
    if geometry == "sphere":
        radius = 0.12
        return (
            "      <visual>\n"
            "        <geometry>\n"
            f"          <sphere radius=\"{radius}\" />\n"
            "        </geometry>\n"
            "      </visual>\n"
        )
    size = [0.4, 0.2, 0.2]
    if isinstance(component.get("dimensions"), (list, tuple)):
        size = [float(v) for v in component["dimensions"][:3]]
    return (
        "      <visual>\n"
        "        <geometry>\n"
        f"          <box size=\"{size[0]:.4f} {size[1]:.4f} {size[2]:.4f}\" />\n"
        "        </geometry>\n"
        "      </visual>\n"
    )


def _derived_links(robot_data: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for component in robot_data.get("components", []):
        component_id = str(component.get("id", "component"))
        if component_id in seen:
            continue
        seen.add(component_id)
        links.append(
            {
                "id": component_id,
                "name": str(component.get("name", component_id)),
                "parent": component.get("parent"),
                "transform": component.get("transform") or {"position": component.get("position", [0.0, 0.0, 0.0]), "rotation": component.get("rotation", [0.0, 0.0, 0.0])},
                "visual": component.get("visual") or {"geometry": "box"},
                "geometry": component.get("geometry") or (component.get("visual") or {}).get("geometry") or "box",
                "mesh": component.get("mesh"),
                "asset_id": component.get("asset_id"),
                "properties": component.get("properties") or {},
                "physics": component.get("physics") or {},
            }
        )
    for link in robot_data.get("links", []):
        link_id = str(link.get("id", "link"))
        if link_id not in {item["id"] for item in links}:
            links.append(link)
    return links


def _derived_joints(robot_data: dict[str, Any]) -> list[dict[str, Any]]:
    joints = list(robot_data.get("joints", []) or [])
    seen = {str(joint.get("id", "")) for joint in joints}
    components = robot_data.get("components", [])
    for component in components:
        parent = component.get("parent")
        if not parent:
            continue
        joint_id = f"joint_{parent}_{component.get('id', 'child')}"
        if joint_id in seen:
            continue
        joints.append(
            {
                "id": joint_id,
                "type": "fixed",
                "parent": parent,
                "child": component.get("id", "child"),
                "axis": [1.0, 0.0, 0.0],
                "origin": component.get("transform") or {"position": component.get("position", [0.0, 0.0, 0.0]), "rotation": component.get("rotation", [0.0, 0.0, 0.0])},
            }
        )
        seen.add(joint_id)
    return joints


def generate_urdf(robot: Any) -> str:
    robot_data = _robot_dict(robot)
    name = str(robot_data.get("name") or robot_data.get("id") or "robot")
    links = _derived_links(robot_data)
    joints = _derived_joints(robot_data)
    asset_map = {str(asset.get("id", asset.get("name", "asset"))): asset for asset in robot_data.get("assets", [])}

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<robot name="{name}">',
    ]

    for link in links:
        link_id = str(link.get("id", "link"))
        link_name = str(link.get("name") or link_id)
        link_pos = _safe_vector((link.get("transform") or {}).get("position") or [0.0, 0.0, 0.0])
        rot = _safe_vector((link.get("transform") or {}).get("rotation") or [0.0, 0.0, 0.0])
        lines.append(f'  <link name="{link_id}">')
        lines.append(f'    <visual name="{link_id}_visual">')
        lines.append(f'      <origin xyz="{link_pos[0]:.6f} {link_pos[1]:.6f} {link_pos[2]:.6f}" rpy="{rot[0]:.6f} {rot[1]:.6f} {rot[2]:.6f}" />')
        lines.append(_link_geometry(link, robot_data))
        lines.append('    </visual>')
        mass = 1.0
        if isinstance(link.get("physics"), dict):
            mass = float(link["physics"].get("mass", mass) or mass)
        lines.append('    <inertial>')
        lines.append(f'      <mass value="{mass:.6f}" />')
        lines.append('      <inertia ixx="1.0" ixy="0.0" ixz="0.0" iyy="1.0" iyz="0.0" izz="1.0" />')
        lines.append('    </inertial>')
        lines.append('  </link>')

        asset_ref = _extract_mesh_path(link, robot_data)
        if asset_ref:
            asset = asset_map.get(asset_ref) or asset_map.get(asset_ref.split('/')[-1].split('\\')[-1])
            if asset and isinstance(asset, dict):
                lines.append(f'  <!-- asset: {asset.get("name", asset_ref)} -->')

    for joint in joints:
        joint_id = str(joint.get("id", "joint"))
        joint_type = str(joint.get("type", "fixed"))
        parent = str(joint.get("parent", "base_link"))
        child = str(joint.get("child", "child_link"))
        axis = joint.get("axis") or [1.0, 0.0, 0.0]
        axis_xyz = " ".join(f"{float(v):.6f}" for v in axis[:3])
        origin = joint.get("origin") or {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}
        origin_pos = _safe_vector((origin or {}).get("position") or [0.0, 0.0, 0.0])
        origin_rot = _safe_vector((origin or {}).get("rotation") or [0.0, 0.0, 0.0])
        lines.append(f'  <joint name="{joint_id}" type="{joint_type}">')
        lines.append(f'    <parent link="{parent}" />')
        lines.append(f'    <child link="{child}" />')
        lines.append(f'    <origin xyz="{origin_pos[0]:.6f} {origin_pos[1]:.6f} {origin_pos[2]:.6f}" rpy="{origin_rot[0]:.6f} {origin_rot[1]:.6f} {origin_rot[2]:.6f}" />')
        lines.append(f'    <axis xyz="{axis_xyz}" />')
        limits = joint.get("limits") or {}
        lower = float(limits.get("lower", 0.0) if isinstance(limits, dict) else 0.0)
        upper = float(limits.get("upper", 0.0) if isinstance(limits, dict) else 0.0)
        if joint_type in {"revolute", "continuous", "prismatic"}:
            lines.append(f'    <limit lower="{lower:.6f}" upper="{upper:.6f}" effort="100.0" velocity="10.0" />')
        lines.append('  </joint>')

    lines.append('</robot>')
    return '\n'.join(lines)
