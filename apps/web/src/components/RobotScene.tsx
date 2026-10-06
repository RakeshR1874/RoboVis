import { Canvas, useLoader } from '@react-three/fiber'
import { OrbitControls, TransformControls } from '@react-three/drei'
import { Component, type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import { DoubleSide } from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import type { RobotConfig } from '../types/robot'

type RobotSceneProps = {
  robot: RobotConfig
  selectedId: string
  onSelect: (id: string) => void
  toolMode: 'select' | 'translate' | 'rotate' | 'scale'
  onTransformChange: (position: [number, number, number], rotation: [number, number, number]) => void
}

const defaultColor = '#8ecae6'

function resolveMeshAssetUrl(component: RobotConfig['components'][number], robot: RobotConfig): string | null {
  const assetKey = component.asset_id ?? component.mesh?.asset ?? component.visual?.mesh ?? null

  if (typeof assetKey === 'string' && assetKey.trim()) {
    const asset = robot.assets?.find((entry) =>
      entry.id === assetKey || entry.filename === assetKey || entry.name === assetKey || entry.uri === assetKey || entry.path === assetKey,
    )
    if (asset?.uri) return asset.uri
    if (assetKey.startsWith('http://') || assetKey.startsWith('https://') || assetKey.startsWith('file://')) return assetKey
    return assetKey.startsWith('/assets/') ? assetKey : `/assets/${assetKey}`
  }

  return null
}

function PrimitiveMesh({ component, selected, onSelect }: { component: RobotConfig['components'][number]; selected: boolean; onSelect: (id: string) => void }) {
  const geometryName = (component.visual?.geometry ?? component.geometry ?? 'box').toLowerCase()
  const color = component.color ?? component.visual?.color ?? defaultColor
  const dims: [number, number, number] = [0.4, 0.2, 0.2]
  const [sx, sy, sz] = dims

  const commonProps = {
    onClick: (event: any) => {
      event.stopPropagation()
      onSelect(component.id)
    },
    position: component.position,
    rotation: component.transform?.rotation ?? component.rotation ?? [0, 0, 0],
  }

  const typeText = (component.type ?? '').toLowerCase()

  // Thruster: cylinder with directional cone
  if (typeText.includes('thruster')) {
    return (
      <group {...commonProps}>
        <mesh>
          <cylinderGeometry args={[0.10, 0.10, 0.28, 20]} />
          <meshStandardMaterial color={selected ? '#ffd166' : color} emissive={selected ? '#ffd166' : '#000000'} emissiveIntensity={selected ? 0.4 : 0.08} />
        </mesh>
        <mesh position={[0.22, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <coneGeometry args={[0.07, 0.18, 18]} />
          <meshStandardMaterial color={selected ? '#7dd3fc' : '#7dd3fc'} emissive={selected ? '#7dd3fc' : '#000000'} emissiveIntensity={0.15} />
        </mesh>
      </group>
    )
  }

  // Battery: box/cube
  if (typeText.includes('battery')) {
    return (
      <mesh {...commonProps}>
        <boxGeometry args={[0.22, 0.12, 0.12]} />
        <meshStandardMaterial color={selected ? '#fbbf24' : color} emissive={selected ? '#fbbf24' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
      </mesh>
    )
  }

  // Joint: axis line marker with rotation indicator
  if (typeText.includes('joint')) {
    // Extract axis from properties if available, default to [1, 0, 0]
    const props = component.properties ?? {}
    const axis = (typeof props.axis === 'object' && Array.isArray(props.axis) 
      ? props.axis 
      : [1, 0, 0]) as [number, number, number]
    
    return (
      <group {...commonProps}>
        {/* Joint center point */}
        <mesh>
          <sphereGeometry args={[0.04, 12, 12]} />
          <meshStandardMaterial color={selected ? '#34d399' : '#10b981'} emissive={selected ? '#34d399' : '#000000'} emissiveIntensity={0.2} />
        </mesh>
        {/* Joint axis indicator - small torus around axis */}
        <mesh scale={[0.15, 0.15, 0.15]} rotation={[
          Math.atan2(axis[1], Math.sqrt(axis[0] * axis[0] + axis[2] * axis[2])),
          Math.atan2(axis[0], axis[2]),
          0
        ]}>
          <torusGeometry args={[0.08, 0.02, 8, 24]} />
          <meshStandardMaterial color={selected ? '#fbbf24' : '#fbbf24'} emissive={selected ? '#fbbf24' : '#000000'} emissiveIntensity={0.2} />
        </mesh>
      </group>
    )
  }

  // Depth Sensor: small cone pointing down
  if (typeText.includes('depth') || typeText.includes('pressure')) {
    return (
      <group {...commonProps}>
        <mesh>
          <sphereGeometry args={[0.08, 12, 12]} />
          <meshStandardMaterial color={selected ? '#67e8f9' : '#06b6d4'} emissive={selected ? '#67e8f9' : '#000000'} emissiveIntensity={selected ? 0.3 : 0.08} />
        </mesh>
        <mesh position={[0, -0.15, 0]}>
          <coneGeometry args={[0.06, 0.16, 12]} />
          <meshStandardMaterial color={selected ? '#0891b2' : '#0891b2'} emissive={selected ? '#0891b2' : '#000000'} emissiveIntensity={0.15} />
        </mesh>
      </group>
    )
  }

  // Sonar/Acoustic Sensor: spiky sphere for sensor
  if (typeText.includes('sonar') || typeText.includes('acoustic')) {
    return (
      <group {...commonProps}>
        <mesh>
          <sphereGeometry args={[0.10, 12, 12]} />
          <meshStandardMaterial color={selected ? '#e879f9' : '#d946ef'} emissive={selected ? '#e879f9' : '#000000'} emissiveIntensity={selected ? 0.3 : 0.08} />
        </mesh>
        {/* Three spike indicators for sonar beam pattern */}
        <mesh position={[0, 0.18, 0]} scale={[0.03, 0.12, 0.03]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color={selected ? '#e879f9' : '#d946ef'} emissive={selected ? '#e879f9' : '#000000'} emissiveIntensity={0.2} />
        </mesh>
        <mesh position={[0.16, 0.09, 0]} scale={[0.03, 0.12, 0.03]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color={selected ? '#e879f9' : '#d946ef'} emissive={selected ? '#e879f9' : '#000000'} emissiveIntensity={0.2} />
        </mesh>
        <mesh position={[-0.16, 0.09, 0]} scale={[0.03, 0.12, 0.03]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color={selected ? '#e879f9' : '#d946ef'} emissive={selected ? '#e879f9' : '#000000'} emissiveIntensity={0.2} />
        </mesh>
      </group>
    )
  }

  // IMU/Inertial Sensor: sphere marker
  if (typeText.includes('imu') || (typeText.includes('sensor') && !typeText.includes('depth'))) {
    return (
      <mesh {...commonProps}>
        <sphereGeometry args={[0.12, 18, 18]} />
        <meshStandardMaterial color={selected ? '#d7b8ff' : color} emissive={selected ? '#d7b8ff' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
      </mesh>
    )
  }

  // Camera: box with frustum cone
  if (typeText.includes('camera')) {
    return (
      <group {...commonProps}>
        <mesh>
          <boxGeometry args={[0.18, 0.12, 0.12]} />
          <meshStandardMaterial color={selected ? '#90f1ef' : color} emissive={selected ? '#90f1ef' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
        </mesh>
        <mesh position={[0.15, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
          <coneGeometry args={[0.07, 0.18, 16]} />
          <meshStandardMaterial color="#f8fafc" emissive="#ffffff" emissiveIntensity={0.1} />
        </mesh>
      </group>
    )
  }

  // Hull: cylinder (common for AUVs)
  if (typeText.includes('hull')) {
    return (
      <mesh {...commonProps}>
        <cylinderGeometry args={[0.15, 0.15, 0.35, 24]} />
        <meshStandardMaterial color={selected ? '#fbbf24' : color} emissive={selected ? '#fbbf24' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
      </mesh>
    )
  }

  // Link: geometric box by default, or configured geometry
  if (typeText.includes('link')) {
    if (geometryName === 'cylinder') {
      return (
        <mesh {...commonProps}>
          <cylinderGeometry args={[Math.max(sx * 0.4, 0.08), Math.max(sx * 0.4, 0.08), Math.max(sz, 0.25), 20]} />
          <meshStandardMaterial color={selected ? '#93c5fd' : color} emissive={selected ? '#93c5fd' : '#000000'} emissiveIntensity={selected ? 0.3 : 0.08} />
        </mesh>
      )
    }
    if (geometryName === 'sphere') {
      return (
        <mesh {...commonProps}>
          <sphereGeometry args={[0.12, 16, 16]} />
          <meshStandardMaterial color={selected ? '#93c5fd' : color} emissive={selected ? '#93c5fd' : '#000000'} emissiveIntensity={selected ? 0.3 : 0.08} />
        </mesh>
      )
    }
    return (
      <mesh {...commonProps}>
        <boxGeometry args={[0.18, 0.12, 0.12]} />
        <meshStandardMaterial color={selected ? '#93c5fd' : color} emissive={selected ? '#93c5fd' : '#000000'} emissiveIntensity={selected ? 0.3 : 0.08} />
      </mesh>
    )
  }

  // Geometry-based fallback
  if (geometryName === 'cylinder') {
    return (
      <mesh {...commonProps}>
        <cylinderGeometry args={[Math.max(sx * 0.5, 0.12), Math.max(sx * 0.5, 0.12), Math.max(sz, 0.2), 24]} />
        <meshStandardMaterial color={selected ? '#ffd166' : color} emissive={selected ? '#ffd166' : '#000000'} emissiveIntensity={selected ? 0.4 : 0.08} />
      </mesh>
    )
  }

  if (geometryName === 'sphere') {
    return (
      <mesh {...commonProps}>
        <sphereGeometry args={[Math.max(Math.max(sx, sy, sz) * 0.5, 0.1), 20, 20]} />
        <meshStandardMaterial color={selected ? '#d7b8ff' : color} emissive={selected ? '#d7b8ff' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
      </mesh>
    )
  }

  if (geometryName === 'capsule') {
    return (
      <mesh {...commonProps}>
        <capsuleGeometry args={[Math.max(Math.min(sx, sy) * 0.5, 0.08), Math.max(sz, 0.15), 8, 16]} />
        <meshStandardMaterial color={selected ? '#90f1ef' : color} emissive={selected ? '#90f1ef' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
      </mesh>
    )
  }

  // Default: box
  return (
    <mesh {...commonProps}>
      <boxGeometry args={[Math.max(sx, 0.12), Math.max(sy, 0.12), Math.max(sz, 0.12)]} />
      <meshStandardMaterial color={selected ? '#6ee7b7' : color} emissive={selected ? '#6ee7b7' : '#000000'} emissiveIntensity={selected ? 0.35 : 0.08} />
    </mesh>
  )
}

class AssetMeshErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback
    }
    return this.props.children
  }
}

function AssetMesh({ url, selected, color }: { url: string; selected: boolean; color: string }) {
  const geometry = useLoader(STLLoader, url)
  return (
    <mesh geometry={geometry} rotation={[0, 0, 0]}>
      <meshStandardMaterial color={selected ? '#ffd166' : color} side={DoubleSide} roughness={0.5} metalness={0.2} emissive={selected ? '#ffd166' : '#000000'} emissiveIntensity={selected ? 0.25 : 0.08} />
    </mesh>
  )
}

function ComponentMesh({
  component,
  robot,
  selected,
  selectedId,
  onSelect,
  toolMode,
  onTransformChange,
}: {
  component: RobotConfig['components'][number]
  robot: RobotConfig
  selected: boolean
  selectedId: string
  onSelect: (id: string) => void
  toolMode: 'select' | 'translate' | 'rotate' | 'scale'
  onTransformChange: (position: [number, number, number], rotation: [number, number, number]) => void
}) {
  const color = component.color ?? component.visual?.color ?? defaultColor
  const [x, y, z] = component.position
  const groupRef = useRef<any>(null)
  const [controlTarget, setControlTarget] = useState<any>(null)
  const meshUrl = useMemo(() => resolveMeshAssetUrl(component, robot), [component, robot])

  useEffect(() => {
    if (selected && groupRef.current) {
      setControlTarget(groupRef.current)
      return
    }

    setControlTarget(null)
  }, [selected, component.id])

  const handleChange = () => {
    if (!groupRef.current) return
    const nextPosition: [number, number, number] = [groupRef.current.position.x, groupRef.current.position.y, groupRef.current.position.z]
    const nextRotation: [number, number, number] = [groupRef.current.rotation.x, groupRef.current.rotation.y, groupRef.current.rotation.z]
    onTransformChange(nextPosition, nextRotation)
  }

  const renderBody = meshUrl ? (
    <AssetMeshErrorBoundary fallback={<PrimitiveMesh component={component} selected={selected} onSelect={onSelect} />}>
      <AssetMesh url={meshUrl} selected={selected} color={color} />
    </AssetMeshErrorBoundary>
  ) : (
    <PrimitiveMesh component={component} selected={selected} onSelect={onSelect} />
  )

  const children = robot.components.filter((child) => child.parent === component.id)

  return (
    <>
      <group
        ref={groupRef}
        position={[x, y, z]}
        rotation={component.transform?.rotation ?? component.rotation ?? [0, 0, 0]}
        onClick={(event) => {
          event.stopPropagation()
          onSelect(component.id)
        }}
      >
        {renderBody}
        {children.map((child) => (
          <ComponentMesh
            key={child.id}
            component={child}
            robot={robot}
            selected={selectedId === child.id}
            selectedId={selectedId}
            onSelect={onSelect}
            toolMode={toolMode}
            onTransformChange={onTransformChange}
          />
        ))}
      </group>

      {selected && toolMode !== 'select' && controlTarget && (
        <TransformControls mode={toolMode} object={controlTarget} onObjectChange={handleChange} />
      )}
    </>
  )
}

export function RobotScene({ robot, selectedId, onSelect, toolMode, onTransformChange }: RobotSceneProps) {
  const roots = robot.components.filter((component) => component.parent === robot.id || !component.parent)

  return (
    <Canvas camera={{ position: [2.4, 2.4, 2.4], fov: 45 }}>
      <color attach="background" args={['#020817']} />
      <ambientLight intensity={0.9} />
      <directionalLight position={[4, 6, 4]} intensity={1.1} />
      <gridHelper args={[12, 12, '#334155', '#1e293b']} />
      <axesHelper args={[2]} />
      <OrbitControls enablePan enableRotate enableZoom />

      {roots
        .filter((component) => component.visible !== false)
        .map((component) => (
          <ComponentMesh
            key={component.id}
            component={component}
            robot={robot}
            selected={selectedId === component.id}
            selectedId={selectedId}
            onSelect={onSelect}
            toolMode={toolMode}
            onTransformChange={onTransformChange}
          />
        ))}
    </Canvas>
  )
}
