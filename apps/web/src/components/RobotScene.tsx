import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html, TransformControls } from '@react-three/drei'
import { useEffect, useRef, useState } from 'react'
import type { RobotConfig } from '../types/robot'

type RobotSceneProps = {
  robot: RobotConfig
  selectedId: string
  onSelect: (id: string) => void
  toolMode: 'select' | 'translate' | 'rotate' | 'scale'
  onTransformChange: (position: [number, number, number], rotation: [number, number, number]) => void
}

const defaultColor = '#8ecae6'

function ComponentMesh({
  component,
  selected,
  onSelect,
  toolMode,
  onTransformChange,
}: {
  component: RobotConfig['components'][number]
  selected: boolean
  onSelect: (id: string) => void
  toolMode: 'select' | 'translate' | 'rotate' | 'scale'
  onTransformChange: (position: [number, number, number], rotation: [number, number, number]) => void
}) {
  const color = component.color ?? defaultColor
  const [x, y, z] = component.position
  const groupRef = useRef<any>(null)
  const [controlTarget, setControlTarget] = useState<any>(null)

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

  const mesh = (() => {
    if (component.type === 'hull') {
      return (
        <mesh
          position={[x, y, z]}
          rotation={[0, 0, Math.PI / 2]}
          onClick={(event) => {
            event.stopPropagation()
            onSelect(component.id)
          }}
        >
          <cylinderGeometry args={[0.18, 0.18, 1.2, 32]} />
          <meshStandardMaterial color={selected ? '#ffd166' : color} emissive={selected ? '#ffd166' : '#000000'} emissiveIntensity={selected ? 0.45 : 0.1} />
        </mesh>
      )
    }

    if (component.type === 'thruster') {
      return (
        <group position={[x, y, z]}>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.05, 0.05, 0.18, 16]} />
            <meshStandardMaterial color={selected ? '#ff784f' : color} emissive={selected ? '#ff784f' : '#000000'} emissiveIntensity={selected ? 0.5 : 0.1} />
          </mesh>
          <mesh position={[0.15, 0, 0]}>
            <sphereGeometry args={[0.035, 12, 12]} />
            <meshStandardMaterial color={selected ? '#fff1ad' : '#e4f1ff'} emissive={selected ? '#fff1ad' : '#000000'} emissiveIntensity={selected ? 0.6 : 0.1} />
          </mesh>
        </group>
      )
    }

    if (component.type === 'battery') {
      return (
        <mesh position={[x, y, z]} onClick={(event) => {
          event.stopPropagation()
          onSelect(component.id)
        }}>
          <boxGeometry args={[0.24, 0.18, 0.12]} />
          <meshStandardMaterial color={selected ? '#6ee7b7' : color} emissive={selected ? '#6ee7b7' : '#000000'} emissiveIntensity={selected ? 0.45 : 0.1} />
        </mesh>
      )
    }

    if (component.type === 'imu' || component.type === 'depth') {
      return (
        <mesh position={[x, y, z]} onClick={(event) => {
          event.stopPropagation()
          onSelect(component.id)
        }}>
          <sphereGeometry args={[0.06, 16, 16]} />
          <meshStandardMaterial color={selected ? '#d7b8ff' : color} emissive={selected ? '#d7b8ff' : '#000000'} emissiveIntensity={selected ? 0.45 : 0.1} />
        </mesh>
      )
    }

    return (
      <mesh position={[x, y, z]} onClick={(event) => {
        event.stopPropagation()
        onSelect(component.id)
      }}>
        <boxGeometry args={[0.12, 0.12, 0.12]} />
        <meshStandardMaterial color={selected ? '#90f1ef' : color} emissive={selected ? '#90f1ef' : '#000000'} emissiveIntensity={selected ? 0.45 : 0.1} />
        <Html distanceFactor={10} position={[0, 0.18, 0]}>
          <div style={{ fontSize: '0.5rem', color: '#dfe7f4', background: 'rgba(5,10,20,0.65)', padding: '2px 4px', borderRadius: '4px' }}>
            {component.name}
          </div>
        </Html>
      </mesh>
    )
  })()

  return (
    <>
      <group ref={groupRef} position={[x, y, z]} onClick={(event) => {
        event.stopPropagation()
        onSelect(component.id)
      }}>
        {mesh}
      </group>

      {selected && toolMode !== 'select' && controlTarget && (
        <TransformControls
          mode={toolMode}
          object={controlTarget}
          onObjectChange={handleChange}
        />
      )}
    </>
  )
}

export function RobotScene({ robot, selectedId, onSelect, toolMode, onTransformChange }: RobotSceneProps) {
  const hull = robot.components.find((component) => component.type === 'hull')

  return (
    <Canvas camera={{ position: [2.4, 2.4, 2.4], fov: 45 }}>
      <color attach="background" args={['#020817']} />
      <ambientLight intensity={0.9} />
      <directionalLight position={[4, 6, 4]} intensity={1.1} />
      <gridHelper args={[12, 12, '#334155', '#1e293b']} />
      <axesHelper args={[2]} />
      <OrbitControls enablePan enableRotate enableZoom />

      {hull && (
        <ComponentMesh
          component={hull}
          selected={selectedId === hull.id}
          onSelect={onSelect}
          toolMode={toolMode}
          onTransformChange={onTransformChange}
        />
      )}

      {robot.components
        .filter((component) => component.id !== 'hull')
        .map((component) => (
          <ComponentMesh
            key={component.id}
            component={component}
            selected={selectedId === component.id}
            onSelect={onSelect}
            toolMode={toolMode}
            onTransformChange={onTransformChange}
          />
        ))}
    </Canvas>
  )
}
