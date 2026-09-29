from __future__ import annotations

from robot.assembly import (
    add_component,
    delete_component,
    duplicate_component,
    get_component_tree,
    update_component_transform,
    validate_component_model,
)
from robot.engineering.engine import compute_engineering_report
from robot.fixtures.auv_001 import create_auv001_fixture
from robot.generators.sdf_generator import generate_sdf


def test_add_and_delete_component():
    robot = create_auv001_fixture()
    added = add_component(robot, {
        "id": "thruster_7",
        "type": "thruster",
        "name": "Thruster 7",
        "parent": "auv_001",
        "transform": {"position": [0.1, 0.2, 0.3], "rotation": [0.0, 0.0, 0.0]},
        "visual": {"enabled": True, "geometry": "cylinder", "mesh": None},
        "physics": {"enabled": True, "mass": 0.8, "volume": 0.001},
        "properties": {"thrust_axis": [1.0, 0.0, 0.0], "max_force": 12.0},
    })

    assert added["components"][-1]["id"] == "thruster_7"
    assert delete_component(added, "thruster_7")["components"][-1]["id"] != "thruster_7"


def test_duplicate_and_parent_child_relationship():
    robot = create_auv001_fixture()
    robot["components"].append({
        "id": "sensor_mast",
        "type": "custom",
        "name": "Sensor Mast",
        "parent": "auv_001",
        "transform": {"position": [0.0, 0.0, 0.3], "rotation": [0.0, 0.0, 0.0]},
        "visual": {"enabled": True, "geometry": "box"},
        "physics": {"enabled": False},
        "properties": {},
        "locked_properties": [],
    })
    robot["components"].append({
        "id": "camera_1",
        "type": "camera",
        "name": "Camera",
        "parent": "sensor_mast",
        "transform": {"position": [0.0, 0.1, 0.8], "rotation": [0.0, 0.0, 0.0]},
        "visual": {"enabled": True, "geometry": "box"},
        "physics": {"enabled": False},
        "properties": {"fov": 70.0},
        "locked_properties": [],
    })

    tree = get_component_tree(robot)
    assert tree["sensor_mast"]["children"][0]["id"] == "camera_1"

    duplicate = duplicate_component(robot, "camera_1")
    assert duplicate["components"][-1]["parent"] == "sensor_mast"
    assert duplicate["components"][-1]["id"] != "camera_1"


def test_duplicate_component_uses_unique_ids_and_preserves_metadata():
    robot = create_auv001_fixture()
    source = next(component for component in robot["components"] if component["type"] == "thruster")
    before_ids = [component["id"] for component in robot["components"]]

    duplicate = duplicate_component(robot, source["id"])
    dup = duplicate["components"][-1]

    assert dup["id"] != source["id"]
    assert dup["id"] not in before_ids
    assert dup["type"] == source["type"]
    assert dup["properties"] == source["properties"]
    assert dup["parent"] == source["parent"]
    assert dup["transform"] == source["transform"]
    assert len([component for component in duplicate["components"] if component["id"] == dup["id"]]) == 1


def test_transform_update_and_locked_property_protection():
    robot = create_auv001_fixture()
    component = robot["components"][0]
    component["locked_properties"] = ["transform.position"]

    updated = update_component_transform(robot, component["id"], {"position": [1.0, 2.0, 3.0], "rotation": [0.1, 0.2, 0.3]})
    assert updated["components"][0]["transform"]["position"] == [0.0, 0.0, 0.0]


def test_component_specific_validation_and_stl_metadata():
    robot = create_auv001_fixture()
    robot["components"].append({
        "id": "battery_2",
        "type": "battery",
        "name": "Battery 2",
        "parent": "auv_001",
        "transform": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]},
        "visual": {"enabled": True, "geometry": "box"},
        "physics": {"enabled": True, "mass": 0.8, "volume": 0.002},
        "properties": {"voltage": 24.0, "capacity": 20.0},
        "locked_properties": [],
        "mesh": {"asset": "battery_2.stl", "scale": [1.0, 1.0, 1.0]},
    })

    issues = validate_component_model(robot)
    assert not any("battery_2" in issue.lower() for issue in issues if "battery" in issue.lower())
    assert robot["components"][-1]["mesh"]["asset"] == "battery_2.stl"


def test_engineering_and_sdf_compatibility_with_component_model():
    robot = create_auv001_fixture()
    report = compute_engineering_report(robot)
    sdf = generate_sdf(robot)

    assert report.buoyancy_status in {"FLOATING", "NEUTRAL", "SINKING"}
    assert '<sdf version="1.10">' in sdf
    assert 'AUV-001' in sdf
