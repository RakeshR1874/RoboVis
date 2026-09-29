from __future__ import annotations

from pytest import approx as pytest_approx

from robot.fixtures.auv_001 import create_auv001_fixture
from robot.engineering.engine import compute_engineering_report


def test_auv_engineering_report_matches_expected_values():
    robot = create_auv001_fixture()
    report = compute_engineering_report(robot)

    assert report.configured.mass == 18.4
    assert report.configured.volume == 0.0848
    assert report.calculated.weight == pytest_approx(180.50, rel=1e-3)
    assert report.calculated.buoyancy == pytest_approx(852.69, rel=1e-3)
    assert report.calculated.net_vertical_force == pytest_approx(672.18, rel=1e-3)
    assert report.buoyancy_status == "FLOATING"
    assert len(report.thruster_forces) == 6


def test_invalid_robot_generates_warnings():
    robot = create_auv001_fixture()
    robot["physical"]["mass"] = -1.0
    robot["physical"]["volume"] = -1.0
    robot["buoyancy"]["fluid_density"] = -5.0

    report = compute_engineering_report(robot)

    assert any("negative mass" in warning.lower() for warning in report.warnings)
    assert any("invalid volume" in warning.lower() for warning in report.warnings)
    assert any("invalid fluid density" in warning.lower() for warning in report.warnings)
