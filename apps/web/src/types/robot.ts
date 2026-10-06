export type Vector3 = [number, number, number]

export interface RobotComponent {
  id: string
  type: string
  name: string
  parent?: string
  position: Vector3
  rotation?: Vector3
  direction: Vector3
  max_force: number
  visible: boolean
  locked: boolean
  enabled?: boolean
  geometry?: string
  color?: string
  asset_id?: string
  transform?: {
    position: Vector3
    rotation: Vector3
  }
  visual?: {
    enabled: boolean
    geometry: string
    mesh?: string | null
    color?: string
  }
  physics?: {
    enabled: boolean
    mass?: number
    volume?: number
    density?: number
    inertia?: Record<string, number>
  }
  properties?: Record<string, unknown>
  locked_properties?: string[]
  mesh?: {
    asset?: string
    scale?: Vector3
  }
}

export interface AssetRecord {
  id: string
  name: string
  filename: string
  path: string
  uri: string
  type: string
  size?: number
  uploaded_at?: string
  metadata?: Record<string, unknown>
}

export interface RobotConfig {
  id: string
  name: string
  physical: {
    mass: number
    volume: number
    density: number
    dimensions: Record<string, number>
    inertia: Record<string, number>
  }
  buoyancy: {
    enabled: boolean
    fluid_density: number
    displacement_volume: number
  }
  controller: {
    type: string
    parameters: Record<string, number | string>
  }
  components: RobotComponent[]
  assets?: AssetRecord[]
}

export interface EngineeringReport {
  configured: {
    mass: number
    volume: number
    density: number
    fluid_density: number
    displacement_volume: number
  }
  calculated: {
    weight: number
    buoyancy: number
    net_vertical_force: number
  }
  buoyancy_status: string
  warnings: string[]
  thruster_forces: Array<{
    component_id: string
    name: string
    max_force: number
    force: number
    direction: [number, number, number]
  }>
}
