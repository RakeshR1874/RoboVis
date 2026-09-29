from robot.fixtures.auv_001 import create_auv001_fixture
from robot.validators.robot_validator import validate_robot_config


def test_example_auv_is_valid():
    robot = create_auv001_fixture()
    issues = validate_robot_config(robot)
    assert issues == []


def test_invalid_mass_is_rejected():
    robot = create_auv001_fixture()
    robot["physical"]["mass"] = 0
    issues = validate_robot_config(robot)
    assert any("mass" in issue.lower() for issue in issues)
