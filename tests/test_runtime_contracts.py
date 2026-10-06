from __future__ import annotations

from fastapi.testclient import TestClient

from robot.fixtures.auv_001 import create_auv001_fixture
from robot.generators.sdf_generator import generate_sdf
from robot.generators.urdf_generator import generate_urdf
from services.api.app.main import app


def test_component_without_mesh_still_generates_generic_geometry():
    robot = create_auv001_fixture()
    robot["components"].append(
        {
            "id": "custom_sensor",
            "type": "sensor",
            "name": "Custom Sensor",
            "parent": "auv_001",
            "position": [0.2, 0.0, 0.3],
            "direction": [1.0, 0.0, 0.0],
            "visual": {"enabled": True, "geometry": "sphere", "mesh": None},
            "physics": {"enabled": True, "mass": 0.12, "volume": 0.0004},
            "properties": {},
            "locked_properties": [],
        }
    )

    sdf = generate_sdf(robot)
    urdf = generate_urdf(robot)

    assert 'custom_sensor' in sdf
    assert '<sphere>' in sdf
    assert 'custom_sensor' in urdf
    assert '<sphere radius=' in urdf or '<box size=' in urdf


def test_component_mesh_reference_uses_robotconfig_asset_uri():
    robot = create_auv001_fixture()
    robot["assets"] = [
        {
            "id": "asset_123",
            "name": "Hull STL",
            "filename": "hull_mesh.stl",
            "path": "/tmp/hull_mesh.stl",
            "uri": "file:///tmp/hull_mesh.stl",
            "type": "stl",
        }
    ]
    robot["components"][0]["asset_id"] = "asset_123"
    robot["components"][0]["mesh"] = {"asset": "asset_123", "scale": [1.0, 1.0, 1.0]}
    robot["components"][0]["visual"]["mesh"] = "asset_123"

    sdf = generate_sdf(robot)
    urdf = generate_urdf(robot)

    assert 'file:///tmp/hull_mesh.stl' in sdf
    assert 'hull_mesh.stl' in urdf or 'file:///tmp/hull_mesh.stl' in urdf


def test_telemetry_ws_streams_data_to_browser():
    client = TestClient(app)
    with client.websocket_connect('/ws/projects/runtime_check/telemetry') as websocket:
        payload = websocket.receive_json()

    assert payload['project_id'] == 'runtime_check'
    assert 'telemetry' in payload
    assert 'ros_topics' in payload['telemetry']
    assert 'gz_topics' in payload['telemetry']
