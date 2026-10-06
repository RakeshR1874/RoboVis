from __future__ import annotations

from typing import Any, Iterable


def normalize_topic_names(raw_topics: Any) -> list[str]:
    if raw_topics is None:
        return []
    if isinstance(raw_topics, str):
        entries = raw_topics.splitlines()
    elif isinstance(raw_topics, (list, tuple, set)):
        entries = raw_topics
    else:
        return []

    normalized: list[str] = []
    for entry in entries:
        if not isinstance(entry, str):
            continue
        topic = entry.strip()
        if topic and not topic.startswith("["):
            normalized.append(topic)
    return sorted(dict.fromkeys(normalized))


def normalize_node_names(raw_nodes: Any) -> list[str]:
    return normalize_topic_names(raw_nodes)


def map_joint_state_message(message: dict[str, Any]) -> dict[str, float]:
    names = message.get("name") or []
    positions = message.get("position") or []
    if not isinstance(names, list) or not isinstance(positions, list):
        return {}
    return {str(name): float(value) for name, value in zip(names, positions)}


def map_tf_message(message: dict[str, Any]) -> dict[str, Any]:
    transforms = message.get("transforms") or message.get("transform") or []
    if isinstance(transforms, dict):
        transforms = [transforms]

    mapped: dict[str, Any] = {}
    for item in transforms:
        if not isinstance(item, dict):
            continue
        child_frame = item.get("child_frame_id") or item.get("child") or "unknown"
        tf = item.get("transform") or item
        translation = tf.get("translation") or {"x": 0.0, "y": 0.0, "z": 0.0}
        rotation = tf.get("rotation") or {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        mapped[str(child_frame)] = {
            "position": [float(translation.get("x", 0.0)), float(translation.get("y", 0.0)), float(translation.get("z", 0.0))],
            "orientation": [float(rotation.get("x", 0.0)), float(rotation.get("y", 0.0)), float(rotation.get("z", 0.0)), float(rotation.get("w", 1.0))],
        }
    return mapped


def runtime_state_from_robot(robot: dict[str, Any], ros_topics: Iterable[str], ros_nodes: Iterable[str], runtime_extra: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = {
        "robot_config_id": robot.get("id"),
        "robot_name": robot.get("name"),
        "components": [
            {
                "id": component.get("id"),
                "type": component.get("type"),
                "position": component.get("position", [0.0, 0.0, 0.0]),
            }
            for component in robot.get("components", [])
        ],
        "ros_topics": normalize_topic_names(list(ros_topics)),
        "ros_nodes": normalize_node_names(list(ros_nodes)),
        "runtime": runtime_extra or {},
    }
    return runtime


def build_foxglove_publish(topic: str, message: dict[str, Any], msg_type: str = "geometry_msgs/msg/Twist") -> dict[str, Any]:
    return {"topic": topic, "type": msg_type, "message": message}
