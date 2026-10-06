"""Fixture robot definitions for the engineering workspace."""
from __future__ import annotations

from robot.fixtures.auv_001 import create_auv001_fixture
from robot.fixtures.empty_robot import create_empty_robot
from robot.fixtures.robotic_arm import create_robotic_arm_fixture


def create_robot_from_template(template: str | None = None) -> dict:
    """
    Create a robot from a template.
    
    Args:
        template: Template name ('empty', 'auv_001', 'robotic_arm').
                  Defaults to 'empty' if None.
    
    Returns:
        Robot configuration dictionary.
    """
    template = (template or "empty").lower().strip()
    
    if template == "auv_001":
        return create_auv001_fixture()
    elif template == "robotic_arm" or template == "arm":
        return create_robotic_arm_fixture()
    else:
        return create_empty_robot()


def list_templates() -> dict[str, str]:
    """Return available robot templates."""
    return {
        "empty": "Empty Robot",
        "auv_001": "AUV Example (6-thruster autonomous underwater vehicle)",
        "robotic_arm": "Robotic Arm (3-link arm with revolute joints)",
    }


__all__ = ["create_robot_from_template", "list_templates", "create_auv001_fixture", "create_empty_robot", "create_robotic_arm_fixture"]
