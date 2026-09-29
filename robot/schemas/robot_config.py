from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Vector3(BaseModel):
    model_config = ConfigDict(extra="allow")

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def from_list(cls, values: list[float] | tuple[float, float, float]) -> "Vector3":
        if len(values) != 3:
            raise ValueError("Vector3 requires exactly three values.")
        return cls(x=values[0], y=values[1], z=values[2])


class PhysicalDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    mass: float = 1.0
    volume: float = 1.0
    density: float = 1000.0
    dimensions: dict[str, float] = Field(default_factory=lambda: {"length": 1.0, "width": 0.3, "height": 0.3})
    inertia: dict[str, float] = Field(default_factory=lambda: {"ix": 1.0, "iy": 1.0, "iz": 1.0})


class BuoyancyConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    fluid_density: float = 1025.0
    displacement_volume: float = 0.0


class ControllerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "pid"
    parameters: dict[str, Any] = Field(default_factory=dict)


class Transform(BaseModel):
    model_config = ConfigDict(extra="allow")

    position: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    geometry: str = "box"
    mesh: str | None = None
    color: str | None = None


class PhysicsSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    mass: float | None = None
    volume: float | None = None
    density: float | None = None
    inertia: dict[str, float] = Field(default_factory=lambda: {"ix": 1.0, "iy": 1.0, "iz": 1.0})


class Component(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    name: str
    parent: str | None = None
    transform: Transform = Field(default_factory=Transform)
    visual: VisualSpec = Field(default_factory=VisualSpec)
    physics: PhysicsSpec = Field(default_factory=PhysicsSpec)
    properties: dict[str, Any] = Field(default_factory=dict)
    locked_properties: list[str] = Field(default_factory=list)
    enabled: bool = True
    visible: bool = True
    locked: bool = False
    color: str | None = None
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    direction: list[float] | None = None
    max_force: float | None = None
    geometry: str | None = None
    mesh: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_component(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        transform = dict(data.get("transform") or {})
        if not transform.get("position"):
            transform["position"] = data.get("position") or [0.0, 0.0, 0.0]
        if not transform.get("rotation"):
            transform["rotation"] = data.get("rotation") or [0.0, 0.0, 0.0]
        data["transform"] = transform

        if "position" not in data:
            data["position"] = list(transform["position"])
        if "rotation" not in data:
            data["rotation"] = list(transform["rotation"])

        visual = dict(data.get("visual") or {})
        if "enabled" not in visual:
            visual["enabled"] = data.get("visible", True)
        if "geometry" not in visual:
            visual["geometry"] = data.get("geometry") or "box"
        data["visual"] = visual

        physics = dict(data.get("physics") or {})
        if "enabled" not in physics:
            physics["enabled"] = data.get("enabled", True)
        data["physics"] = physics

        properties = dict(data.get("properties") or {})
        if data.get("type") == "thruster" and "thrust_axis" not in properties:
            direction = data.get("direction") or [1.0, 0.0, 0.0]
            properties["thrust_axis"] = direction
        if data.get("type") == "thruster" and "max_force" not in properties and data.get("max_force") is not None:
            properties["max_force"] = data["max_force"]
        data["properties"] = properties

        if "locked_properties" not in data:
            data["locked_properties"] = []
        return data


class RobotConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    physical: PhysicalDefinition = Field(default_factory=PhysicalDefinition)
    components: list[Component] = Field(default_factory=list)
    buoyancy: BuoyancyConfig = Field(default_factory=BuoyancyConfig)
    controller: ControllerConfig = Field(default_factory=ControllerConfig)
