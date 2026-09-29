from robot.fixtures.auv_001 import create_auv001_fixture
from robot.generators.sdf_generator import generate_sdf


def test_generated_sdf_contains_expected_components():
    robot = create_auv001_fixture()
    sdf = generate_sdf(robot)

    assert 'AUV-001' in sdf
    assert 'hull' in sdf
    assert 'thruster_1' in sdf
    assert 'thruster_6' in sdf
    assert 'battery' in sdf
    assert 'imu' in sdf
    assert 'depth_sensor' in sdf
    assert '<sdf version="1.10">' in sdf
