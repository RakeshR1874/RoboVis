from __future__ import annotations

from fastapi.testclient import TestClient

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
from robot.generators.urdf_generator import generate_urdf
from robot.schemas.robot_config import RobotConfig
from services.api.app.main import app


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


def test_generic_robot_model_supports_assets_links_and_joints():
    robot = RobotConfig(
        id="arm_01",
        name="Arm Test",
        components=[
            {
                "id": "base_link",
                "type": "base",
                "name": "Base",
                "transform": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]},
                "visual": {"enabled": True, "geometry": "box", "mesh": "base.stl"},
                "physics": {"enabled": True, "mass": 2.0},
            },
            {
                "id": "joint_1",
                "type": "joint_controller",
                "name": "Joint 1",
                "parent": "base_link",
                "visual": {"enabled": False, "geometry": "box"},
                "physics": {"enabled": False},
            },
        ],
        links=[
            {"id": "base_link", "name": "Base Link", "parent": None, "transform": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}},
            {"id": "arm_link", "name": "Arm Link", "parent": "base_link", "transform": {"position": [0.1, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}},
        ],
        joints=[
            {"id": "joint_1", "type": "revolute", "parent": "base_link", "child": "arm_link", "axis": [0.0, 0.0, 1.0], "limits": {"lower": -1.57, "upper": 1.57}, "initial_position": 0.0},
        ],
        actuators=[{"id": "actuator_1", "type": "servo", "joint": "joint_1", "max_torque": 2.5}],
        sensors=[{"id": "imu_1", "type": "imu", "frame": "base_link", "transform": {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}}],
        assets=[{"id": "mesh_1", "type": "stl", "path": "assets/base.stl", "name": "Base STL", "scale": [1.0, 1.0, 1.0]}],
    )

    urdf = generate_urdf(robot)
    assert '<robot name="Arm Test"' in urdf
    assert '<joint name="joint_1" type="revolute">' in urdf
    assert 'assets/base.stl' in urdf or 'base.stl' in urdf
    assert 'arm_link' in urdf


def test_robot_artifacts_route_generates_sdf_and_urdf_payloads():
    client = TestClient(app)
    payload = create_auv001_fixture()
    payload["components"][0]["mesh"] = {"asset": "asset_hull_001", "scale": [1.0, 1.0, 1.0]}
    payload["components"][0]["visual"]["mesh"] = {"asset": "asset_hull_001", "scale": [1.0, 1.0, 1.0]}
    payload["assets"] = [{"id": "asset_hull_001", "name": "Hull STL", "path": "/tmp/hull.stl", "uri": "file:///tmp/hull.stl", "type": "stl"}]

    response = client.post("/api/robot/artifacts", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert '<sdf version="1.10">' in body["sdf"]
    assert '<robot name="AUV-001"' in body["urdf"]
    assert 'hull.stl' in body["urdf"] or 'tmp/hull.stl' in body["urdf"] or 'asset_hull_001' in body["urdf"]


def test_valid_stl_upload_and_asset_assignment_round_trip():
    client = TestClient(app)
    stl_payload = b"""solid hull\nfacet normal 0 0 1\n  outer loop\n    vertex 0 0 0\n    vertex 1 0 0\n    vertex 0 1 0\n  endloop\nendfacet\nendsolid hull\n"""
    upload = client.post(
        "/api/assets/upload",
        files={"file": ("hull_uploaded.stl", stl_payload, "model/stl")},
    )
    assert upload.status_code == 200, upload.text
    asset = upload.json()["asset"]
    assert asset["filename"].endswith(".stl")

    listed = client.get("/api/assets")
    assert listed.status_code == 200
    listed_ids = {entry["id"] for entry in listed.json()["assets"]}
    assert asset["id"] in listed_ids

    robot = create_auv001_fixture()
    robot["assets"] = [
        {"id": asset["id"], "name": asset["name"], "path": asset["path"], "uri": asset["uri"], "type": "stl"}
    ]
    robot["components"][0]["asset_id"] = asset["id"]
    robot["components"][0]["mesh"] = {"asset": asset["id"], "scale": [1.0, 1.0, 1.0]}
    robot["components"][0]["visual"]["mesh"] = {"asset": asset["id"], "scale": [1.0, 1.0, 1.0]}

    artifacts = client.post("/api/robot/artifacts", json=robot)
    assert artifacts.status_code == 200
    body = artifacts.json()
    assert asset["filename"] in body["urdf"] or asset["id"] in body["urdf"] or asset["path"] in body["urdf"]
    assert asset["filename"] in body["sdf"] or asset["id"] in body["sdf"] or asset["path"] in body["sdf"]


def test_invalid_placeholder_stl_upload_is_rejected():
    client = TestClient(app)
    invalid = b"solid test\nendsolid test\n"
    response = client.post(
        "/api/assets/upload",
        files={"file": ("placeholder.stl", invalid, "model/stl")},
    )

    assert response.status_code == 400
    assert "valid STL" in response.json()["detail"]
