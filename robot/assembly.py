from __future__ import annotations

import copy
from typing import Any


def _default_transform(position: Any = None, rotation: Any = None) -> dict[str, list[float]]:
    return {
        "position": [float(v) for v in (position or [0.0, 0.0, 0.0])[:3]],
        "rotation": [float(v) for v in (rotation or [0.0, 0.0, 0.0])[:3]],
    }


def normalize_component(component: dict[str, Any]) -> dict[str, Any]:
    component = copy.deepcopy(component)
    transform = dict(component.get("transform") or {})
    if not transform.get("position"):
        transform["position"] = component.get("position") or [0.0, 0.0, 0.0]
    if not transform.get("rotation"):
        transform["rotation"] = component.get("rotation") or [0.0, 0.0, 0.0]
    component["transform"] = _default_transform(transform.get("position"), transform.get("rotation"))

    if component.get("type") == "thruster":
        properties = dict(component.get("properties") or {})
        if "thrust_axis" not in properties:
            direction = component.get("direction")
            if direction is not None:
                properties["thrust_axis"] = list(direction)
            else:
                properties["thrust_axis"] = [1.0, 0.0, 0.0]
        if "max_force" not in properties:
            max_force = component.get("max_force")
            if max_force is not None:
                properties["max_force"] = float(max_force)
        component["properties"] = properties

    visual = dict(component.get("visual") or {})
    if "enabled" not in visual and "visible" in component:
        visual["enabled"] = bool(component.get("visible", True))
    if "geometry" not in visual:
        visual["geometry"] = component.get("geometry") or "box"
    component["visual"] = visual

    physics = dict(component.get("physics") or {})
    if "enabled" not in physics:
        physics["enabled"] = bool(component.get("enabled", True))
    if "mass" not in physics and component.get("mass") is not None:
        physics["mass"] = float(component["mass"])
    if "volume" not in physics and component.get("volume") is not None:
        physics["volume"] = float(component["volume"])
    component["physics"] = physics

    component.setdefault("parent", None)
    component.setdefault("enabled", True)
    component.setdefault("visible", True)
    component.setdefault("locked_properties", [])
    component.setdefault("properties", {})
    if "mesh" not in component:
        component["mesh"] = None
    if component.get("mesh") is not None and isinstance(component["mesh"], dict):
        component["mesh"].setdefault("asset", "")
        component["mesh"].setdefault("scale", [1.0, 1.0, 1.0])
    if "position" not in component:
        component["position"] = list(component["transform"]["position"])
    if "rotation" not in component:
        component["rotation"] = list(component["transform"]["rotation"])
    return component


def ensure_robot_shape(robot: Any) -> dict[str, Any]:
    if not isinstance(robot, dict):
        return robot.model_dump(mode="json") if hasattr(robot, "model_dump") else {"id": "auv", "name": "AUV", "components": []}
    robot = copy.deepcopy(robot)
    robot.setdefault("id", "auv")
    robot.setdefault("name", "AUV")
    robot.setdefault("components", [])
    robot["components"] = [normalize_component(component) for component in robot["components"]]
    return robot


def add_component(robot: Any, component_data: dict[str, Any]) -> dict[str, Any]:
    robot = ensure_robot_shape(robot)
    component = normalize_component(component_data)
    if not component.get("id"):
        base = component.get("type", "component")
        component["id"] = f"{base}_{len(robot['components']) + 1}"
    robot["components"].append(component)
    return robot


def delete_component(robot: Any, component_id: str) -> dict[str, Any]:
    robot = ensure_robot_shape(robot)
    new_components = []
    for component in robot["components"]:
        if component.get("id") == component_id:
            continue
        if component.get("parent") == component_id:
            component["parent"] = None
        new_components.append(component)
    robot["components"] = new_components
    return robot


def duplicate_component(robot: Any, component_id: str) -> dict[str, Any]:
    robot = ensure_robot_shape(robot)
    for component in robot["components"]:
        if component.get("id") == component_id:
            clone = copy.deepcopy(component)
            base = (component.get("type") or "component").lower().replace(" ", "_")
            suffix = 1
            while True:
                candidate = f"{base}_{suffix}"
                if not any(item.get("id") == candidate for item in robot["components"]):
                    clone["id"] = candidate
                    break
                suffix += 1
            clone["name"] = f"{component.get('name', base)} Copy"
            clone["parent"] = component.get("parent")
            clone["transform"] = copy.deepcopy(component.get("transform", {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}))
            clone["position"] = list(clone["transform"]["position"])
            clone["rotation"] = list(clone["transform"]["rotation"])
            robot["components"].append(clone)
            return robot
    return robot


def update_component_transform(robot: Any, component_id: str, transform_update: dict[str, Any]) -> dict[str, Any]:
    robot = ensure_robot_shape(robot)
    for component in robot["components"]:
        if component.get("id") != component_id:
            continue
        locked = set(component.get("locked_properties", []))
        if "transform.position" in locked and "position" in transform_update:
            transform_update = {k: v for k, v in transform_update.items() if k != "position"}
        if "transform.rotation" in locked and "rotation" in transform_update:
            transform_update = {k: v for k, v in transform_update.items() if k != "rotation"}
        current_transform = dict(component.get("transform") or {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]})
        if "position" in transform_update:
            current_transform["position"] = [float(value) for value in transform_update["position"][:3]]
        if "rotation" in transform_update:
            current_transform["rotation"] = [float(value) for value in transform_update["rotation"][:3]]
        component["transform"] = current_transform
        component["position"] = list(current_transform["position"])
        component["rotation"] = list(current_transform["rotation"])
        return robot
    return robot


def get_component_tree(robot: Any) -> dict[str, Any]:
    robot = ensure_robot_shape(robot)
    root_children: dict[str, Any] = {}
    for component in robot["components"]:
        root = component.get("parent") or robot.get("id", "root")
        root_children.setdefault(root, []).append(component)
    result: dict[str, Any] = {}
    for component in robot["components"]:
        if component.get("parent") is None:
            result[component["id"]] = {"component": component, "children": []}
    for component in robot["components"]:
        parent_id = component.get("parent")
        if parent_id in result:
            result[parent_id]["children"].append({"id": component["id"], "component": component, "children": []})
    for component in robot["components"]:
        parent_id = component.get("parent")
        if parent_id and parent_id not in result:
            result.setdefault(parent_id, {"component": None, "children": []})
            result[parent_id]["children"].append({"id": component["id"], "component": component, "children": []})
    return result


def validate_component_model(robot: Any) -> list[str]:
    robot = ensure_robot_shape(robot)
    items = robot.get("components", [])
    valid_ids = {item.get("id") for item in items}
    valid_ids.add(robot.get("id"))
    issues: list[str] = []
    seen: set[str] = set()
    for component in items:
        component = normalize_component(component)
        cid = component.get("id")
        if not cid:
            issues.append("Each component must have an id.")
            continue
        if cid in seen:
            issues.append(f"Duplicate component id: {cid}")
        seen.add(cid)
        comp_type = component.get("type")
        if not comp_type:
            issues.append(f"Component {cid} must declare a type.")
        parent_id = component.get("parent")
        if parent_id and parent_id not in valid_ids:
            issues.append(f"Component {cid} references an unknown parent: {parent_id}")
        transform = component.get("transform") or {}
        position = transform.get("position", [0.0, 0.0, 0.0])
        rotation = transform.get("rotation", [0.0, 0.0, 0.0])
        if len(position) != 3 or len(rotation) != 3:
            issues.append(f"Component {cid} transform must contain 3D position and rotation arrays.")
        if comp_type == "thruster":
            props = component.get("properties") or {}
            if "thrust_axis" not in props and "direction" not in component:
                issues.append(f"Thruster {cid} must define a thrust axis.")
            if "max_force" in props and float(props["max_force"]) < 0:
                issues.append(f"Thruster {cid} max force must be non-negative.")
        if comp_type == "battery":
            if component.get("properties", {}).get("voltage") is not None and float(component["properties"]["voltage"]) < 0:
                issues.append(f"Battery {cid} voltage must be non-negative.")
        if component.get("locked_properties") is not None and not isinstance(component["locked_properties"], list):
            issues.append(f"Component {cid} locked properties must be a list.")
        mesh = component.get("mesh")
        if mesh is not None and not isinstance(mesh, dict):
            issues.append(f"Component {cid} mesh metadata must be a dictionary when present.")
    return issues
