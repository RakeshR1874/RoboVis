from __future__ import annotations

from services.api.app.ros_runtime import (
    build_foxglove_publish,
    map_joint_state_message,
    map_tf_message,
    normalize_topic_names,
    runtime_state_from_robot,
)


def test_runtime_mode_selection_contract() -> None:
    topics = normalize_topic_names(["/rosout", "", "/tf", "/rosout"])
    assert topics == ["/rosout", "/tf"]


def test_ros_connection_state_tracks_real_topics() -> None:
    state = runtime_state_from_robot({"id": "auv-1", "name": "AUV-1", "components": [{"id": "hull", "type": "hull", "position": [0.0, 0.0, 0.0]}]}, ["/rosout", "/tf"], ["/node_1"])
    assert state["robot_config_id"] == "auv-1"
    assert state["ros_topics"] == ["/rosout", "/tf"]
    assert state["ros_nodes"] == ["/node_1"]


def test_runtime_state_is_separate_from_robot_config() -> None:
    robot = {"id": "auv-1", "name": "AUV-1", "components": [{"id": "hull", "type": "hull", "position": [0.0, 0.0, 0.0]}]}
    runtime = runtime_state_from_robot(robot, ["/rosout"], ["/node_1"], {"pose": {"position": [0.1, 0.0, 0.0]}})
    assert runtime["robot_config_id"] == robot["id"]
    assert runtime["runtime"]["pose"]["position"] == [0.1, 0.0, 0.0]
    assert runtime["components"][0]["position"] == [0.0, 0.0, 0.0]


def test_joint_state_message_is_mapped_to_joint_positions() -> None:
    message = {"name": ["joint_1", "joint_2"], "position": [0.125, -0.5]}
    mapped = map_joint_state_message(message)
    assert mapped["joint_1"] == 0.125
    assert mapped["joint_2"] == -0.5


def test_tf_message_map_keeps_transform_state() -> None:
    message = {"transforms": [{"child_frame_id": "thruster_1", "transform": {"translation": {"x": 1.0, "y": 0.0, "z": 0.0}, "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}}]}
    mapped = map_tf_message(message)
    assert mapped["thruster_1"]["position"] == [1.0, 0.0, 0.0]
    assert mapped["thruster_1"]["orientation"][-1] == 1.0


def test_foxglove_command_publish_interface_is_valid() -> None:
    payload = build_foxglove_publish("/auv/dev/cmd_vel", {"linear": {"x": 1.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.5}})
    assert payload["topic"] == "/auv/dev/cmd_vel"
    assert payload["type"] == "geometry_msgs/msg/Twist"
    assert payload["message"]["angular"]["z"] == 0.5
    assert "op" not in payload
