import { Component, type ReactNode, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { DoubleSide } from 'three'
import './App.css'
import { generateRobotArtifacts, getAssets, getRobot, getRobotEngineering, resetRobot, resetSimulation, runSimulation, saveRobot, stopSimulation, uploadAsset, validateRobot } from './api/client'
import { RobotScene } from './components/RobotScene'
import { TemplateSelector } from './components/TemplateSelector'
import type { AssetRecord, EngineeringReport, RobotComponent, RobotConfig } from './types/robot'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

const cloneRobot = (robot: RobotConfig): RobotConfig => JSON.parse(JSON.stringify(robot))

type RuntimeMode = 'OFFLINE_PREVIEW' | 'ROS_LIVE' | 'SIMULATION'

function AssetPreview({ asset }: { asset: AssetRecord | null }) {
  if (!asset) {
    return <div className="validation-card">No STL selected</div>
  }

  return (
    <div style={{ height: 190, borderRadius: 8, overflow: 'hidden', border: '1px solid #334155' }}>
      <Canvas camera={{ position: [0, 0.5, 2.2], fov: 40 }}>
        <color attach="background" args={['#020817']} />
        <ambientLight intensity={0.8} />
        <directionalLight position={[2, 2, 2]} intensity={1.2} />
        <group rotation={[-Math.PI / 2, 0, 0]} scale={0.05}>
          <AssetMeshErrorBoundary fallback={<mesh><boxGeometry args={[1, 1, 1]} /><meshStandardMaterial color="#7dd3fc" /></mesh>}>
            <AssetMesh url={asset.uri || `/assets/${asset.filename}`} />
          </AssetMeshErrorBoundary>
        </group>
        <OrbitControls enablePan enableRotate enableZoom />
      </Canvas>
    </div>
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

function AssetMesh({ url }: { url: string }) {
  const geometry = useLoader(STLLoader, url)
  return (
    <mesh geometry={geometry} rotation={[0, 0, 0]}>
      <meshStandardMaterial color="#7dd3fc" side={DoubleSide} roughness={0.5} metalness={0.2} />
    </mesh>
  )
}

function App() {
  const [robot, setRobot] = useState<RobotConfig | null>(null)
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)
  const [selectedId, setSelectedId] = useState('hull')
  const [history, setHistory] = useState<RobotConfig[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [issues, setIssues] = useState<string[]>([])
  const [status, setStatus] = useState('Loading robot...')
  const [runtimeState, setRuntimeState] = useState<'idle' | 'running' | 'stopped'>('idle')
  const [runtimeMode, setRuntimeMode] = useState<RuntimeMode>('OFFLINE_PREVIEW')
  const [rosBridgeUrl, setRosBridgeUrl] = useState('ws://localhost:8765')
  const [rosConnectionStatus, setRosConnectionStatus] = useState<'DISCONNECTED' | 'LIVE'>('DISCONNECTED')
  const [engineeringReport, setEngineeringReport] = useState<EngineeringReport | null>(null)
  const [toolMode, setToolMode] = useState<'select' | 'translate' | 'rotate' | 'scale'>('select')
  const [assets, setAssets] = useState<AssetRecord[]>([])
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null)
  const [telemetry, setTelemetry] = useState<Record<string, unknown> | null>(null)
  const [telemetryStatus, setTelemetryStatus] = useState<'DISCONNECTED' | 'LIVE'>('DISCONNECTED')
  const [rosTopics, setRosTopics] = useState<Array<{ topic: string; type: string; count: number; rate: number; latest: unknown }>>([])
  const rosSocketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let cancelled = false

    void getRobot()
      .then((initialRobot) => {
        if (cancelled) return
        setRobot(initialRobot)
        setSelectedId(initialRobot.components[0]?.id ?? 'hull')
        setHistory([cloneRobot(initialRobot)])
        setHistoryIndex(0)
        setStatus('Ready')
      })
      .catch((error) => {
        if (cancelled) return
        setStatus(error instanceof Error ? error.message : 'Failed to load robot')
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    void getAssets()
      .then((nextAssets) => {
        if (cancelled) return
        setAssets(nextAssets)
        if (!selectedAssetId && nextAssets[0]) {
          setSelectedAssetId(nextAssets[0].id)
        }
      })
      .catch(() => {
        if (!cancelled) setAssets([])
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!robot?.id) return

    void getRobotEngineering()
      .then((report) => setEngineeringReport(report))
      .catch(() => setEngineeringReport(null))
  }, [robot?.id])

  useEffect(() => {
    if (!robot) return

    void validateRobot(robot)
      .then((robotIssues) => setIssues(robotIssues))
      .catch((error) => setIssues([error instanceof Error ? error.message : 'Validation failed']))
  }, [robot])

  useEffect(() => {
    if (runtimeMode === 'ROS_LIVE') {
      if (!rosBridgeUrl) {
        setRosConnectionStatus('DISCONNECTED')
        return
      }
      const socket = new WebSocket(rosBridgeUrl, ['foxglove.websocket.v1'])
      socket.binaryType = 'arraybuffer'
      rosSocketRef.current = socket
      setRosConnectionStatus('LIVE')

      const decodeFoxglovePayload = (raw: unknown): Record<string, unknown> | null => {
        if (typeof raw === 'string') {
          try {
            return JSON.parse(raw) as Record<string, unknown>
          } catch {
            return null
          }
        }

        if (raw instanceof ArrayBuffer) {
          const bytes = new Uint8Array(raw)
          const text = new TextDecoder().decode(bytes)
          const jsonStart = text.search(/[\[{]/)
          if (jsonStart <= 0) {
            return null
          }
          try {
            return JSON.parse(text.slice(jsonStart)) as Record<string, unknown>
          } catch {
            return null
          }
        }

        return null
      }

      let nextSubscriptionId = 1

      const subscribeTopics = async () => {
        try {
          const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'}/api/ros/discovery`)
          const payload = await response.json() as { topics?: string[] }
          const topics = Array.isArray(payload.topics) ? payload.topics : []
          if (topics.length === 0) {
            return
          }
          const preferredTopics = topics.filter((topic) => topic.includes('/foxglove_bridge') || topic.startsWith('/rosout') || topic.startsWith('/parameter_events') || topic.startsWith('/tf') || topic.startsWith('/joint_states'))
          const nextTopics = preferredTopics.length > 0 ? preferredTopics : topics.slice(0, 3)
          if (!nextTopics.includes('/foxglove_bridge/sysinfo')) {
            nextTopics.push('/foxglove_bridge/sysinfo')
          }
          // The actual subscription IDs are assigned only after the server advertises a valid channel list.
        } catch {
          setRosConnectionStatus('DISCONNECTED')
        }
      }

      socket.addEventListener('open', () => {
        setRosConnectionStatus('LIVE')
        void subscribeTopics()
      })
      socket.addEventListener('message', (event) => {
        try {
          const payload = decodeFoxglovePayload(event.data)
          if (!payload) {
            setTelemetry({ source: 'ros', message: event.data })
            return
          }

          if (payload.op === 'advertise') {
            const channels = Array.isArray((payload as any).channels) ? (payload as any).channels : []
            channels.forEach((channel: Record<string, unknown>) => {
              const topic = String(channel.topic ?? '')
              if (!topic) return
              setRosTopics((previous) => {
                const existing = previous.find((entry) => entry.topic === topic)
                return [
                  ...previous.filter((entry) => entry.topic !== topic),
                  {
                    topic,
                    type: String(channel.encoding ?? existing?.type ?? 'unknown'),
                    count: existing?.count ?? 0,
                    rate: existing?.rate ?? 0,
                    latest: existing?.latest ?? null,
                  },
                ]
              })
              if (topic.includes('/foxglove_bridge') || topic.startsWith('/rosout') || topic.startsWith('/parameter_events') || topic.startsWith('/tf') || topic.startsWith('/joint_states')) {
                const channelId = Number(channel.id ?? 0)
                if (channelId > 0) {
                  socket.send(JSON.stringify({ op: 'subscribe', subscriptions: [{ id: nextSubscriptionId++, channelId }] }))
                }
              }
            })
            return
          }

          if (payload.op === 'messageData') {
            const message = (payload as any).data ?? payload
            setTelemetry({ source: 'ros', message })
            setRosTopics((previous) => {
              const topic = previous[previous.length - 1]?.topic ?? '/ros/live'
              const existing = previous.find((entry) => entry.topic === topic)
              const nextCount = (existing?.count ?? 0) + 1
              return [
                ...previous.filter((entry) => entry.topic !== topic),
                {
                  topic,
                  type: existing?.type ?? 'unknown',
                  count: nextCount,
                  rate: Math.max(0, nextCount / 10),
                  latest: message,
                },
              ]
            })
            return
          }

          if (payload.process_memory !== undefined || payload.process_cpu_percent !== undefined || payload.total_memory !== undefined) {
            setTelemetry({ source: 'ros', topic: '/foxglove_bridge/sysinfo', message: payload })
            setRosTopics((previous) => {
              const topic = '/foxglove_bridge/sysinfo'
              const existing = previous.find((entry) => entry.topic === topic)
              const nextCount = (existing?.count ?? 0) + 1
              return [
                ...previous.filter((entry) => entry.topic !== topic),
                {
                  topic,
                  type: existing?.type ?? 'json',
                  count: nextCount,
                  rate: Math.max(0, nextCount / 10),
                  latest: payload,
                },
              ]
            })
            return
          }

          setTelemetry(payload)
        } catch {
          setTelemetry({ source: 'ros', message: event.data })
        }
      })
      socket.addEventListener('close', () => {
        setRosConnectionStatus('DISCONNECTED')
        setTelemetry(null)
        setRosTopics([])
      })
      socket.addEventListener('error', () => {
        setRosConnectionStatus('DISCONNECTED')
        setTelemetry(null)
        setRosTopics([])
      })
      return () => {
        socket.close()
        rosSocketRef.current = null
      }
    }

    if (runtimeState !== 'running' || !robot?.id) {
      setTelemetryStatus('DISCONNECTED')
      setTelemetry(null)
      return
    }

    const socket = new WebSocket(`ws://127.0.0.1:8000/ws/projects/${encodeURIComponent(robot.id)}/telemetry`)
    setTelemetryStatus('LIVE')

    socket.addEventListener('open', () => setTelemetryStatus('LIVE'))
    socket.addEventListener('message', (event) => {
      try {
        const payload = JSON.parse(event.data) as Record<string, unknown>
        setTelemetry(payload)
      } catch {
        setTelemetry(null)
      }
    })
    socket.addEventListener('close', () => {
      setTelemetryStatus('DISCONNECTED')
      setTelemetry(null)
    })
    socket.addEventListener('error', () => {
      setTelemetryStatus('DISCONNECTED')
      setTelemetry(null)
    })

    return () => socket.close()
  }, [runtimeMode, rosBridgeUrl, runtimeState, robot?.id])

  const selectedComponent = useMemo(
    () => robot?.components.find((component) => component.id === selectedId) ?? null,
    [robot, selectedId],
  )

  const commitRobot = (updater: (value: RobotConfig) => RobotConfig) => {
    setRobot((currentRobot) => {
      if (!currentRobot) return currentRobot

      const nextRobot = updater(cloneRobot(currentRobot))

      setHistoryIndex((previousIndex) => {
        const nextIndex = previousIndex + 1
        setHistory((previousHistory) => [
          ...previousHistory.slice(0, previousIndex + 1),
          cloneRobot(nextRobot),
        ])
        return nextIndex
      })

      return nextRobot
    })
  }

  const handleUndo = () => {
    if (historyIndex <= 0 || !robot) return
    const nextIndex = historyIndex - 1
    const previousRobot = cloneRobot(history[nextIndex])
    setRobot(previousRobot)
    setHistoryIndex(nextIndex)
    setSelectedId(previousRobot.components.find((component) => component.id === selectedId)?.id ?? previousRobot.components[0]?.id ?? 'hull')
    setStatus('Reverted to previous state')
  }

  const handleRedo = () => {
    if (historyIndex >= history.length - 1 || !robot) return
    const nextIndex = historyIndex + 1
    const nextRobot = cloneRobot(history[nextIndex])
    setRobot(nextRobot)
    setHistoryIndex(nextIndex)
    setSelectedId(nextRobot.components.find((component) => component.id === selectedId)?.id ?? nextRobot.components[0]?.id ?? 'hull')
    setStatus('Restored state from history')
  }

  const handleSave = async () => {
    if (!robot) return
    try {
      const savedRobot = await saveRobot(robot)
      setRobot(savedRobot)
      setHistory((previousHistory) => {
        const snapshot = cloneRobot(savedRobot)
        const nextHistory = [...previousHistory.slice(0, historyIndex + 1), snapshot]
        return nextHistory.length > 1 && JSON.stringify(nextHistory[nextHistory.length - 2]) === JSON.stringify(snapshot)
          ? nextHistory.slice(0, -1)
          : nextHistory
      })
      setStatus('Saved successfully')
      setRuntimeState('stopped')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to save robot')
    }
  }

  const handleRun = async () => {
    if (!robot) return

    const nextIssues = await validateRobot(robot)
    if (nextIssues.length > 0) {
      setIssues(nextIssues)
      setStatus('Run blocked: validation failed')
      setRuntimeState('stopped')
      return
    }

    try {
      await generateRobotArtifacts(robot)
      const simulation = await runSimulation()
      setIssues([])
      setRuntimeState(simulation.status === 'RUNNING' ? 'running' : 'stopped')
      setStatus(simulation.details || 'Simulation running')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to launch simulation')
      setRuntimeState('stopped')
    }
  }

  const handleStop = async () => {
    try {
      const simulation = await stopSimulation()
      setRuntimeState(simulation.status === 'STOPPED' ? 'stopped' : 'idle')
      setStatus(simulation.details || 'Simulation stopped')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to stop simulation')
    }
  }

  const handleReset = async () => {
    try {
      const freshRobot = await resetRobot()
      await resetSimulation()
      setRobot(freshRobot)
      setIssues([])
      setRuntimeState('idle')
      setHistory([cloneRobot(freshRobot)])
      setHistoryIndex(0)
      setSelectedId(freshRobot.components[0]?.id ?? 'hull')
      setStatus('Workspace reset')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to reset robot')
    }
  }

  const handleAddComponent = (type: string) => {
    if (!robot) return

    const suffix = `${Date.now()}`.slice(-6)
    const componentId = `${type}_${suffix}`
    const robotComponent: RobotComponent = {
      id: componentId,
      type,
      name: `${type.charAt(0).toUpperCase()}${type.slice(1)} ${suffix}`,
      parent: robot.id,
      position: [0, 0, 0],
      direction: [1, 0, 0],
      max_force: type === 'thruster' ? 10 : 0,
      visible: true,
      locked: false,
      enabled: true,
      geometry: type === 'hull' ? 'cylinder' : type === 'battery' ? 'box' : 'box',
      color: '#8ecae6',
      transform: { position: [0, 0, 0], rotation: [0, 0, 0] },
      visual: { enabled: true, geometry: type === 'hull' ? 'cylinder' : 'box', mesh: null, color: '#8ecae6' },
      physics: { enabled: true, mass: 0.2, volume: 0.0005 },
      properties: type === 'thruster' ? { thrust_axis: [1, 0, 0], max_force: 10 } : {},
      locked_properties: [],
    } as RobotComponent

    commitRobot((draftRobot) => ({
      ...draftRobot,
      components: [...draftRobot.components, robotComponent],
    }))
    setSelectedId(componentId)
  }

  const handleDeleteSelected = () => {
    if (!selectedComponent || !robot) return

    let nextSelection = 'hull'

    commitRobot((draftRobot) => {
      const remainingComponents = draftRobot.components.filter((component) => component.id !== selectedComponent.id)
      nextSelection = remainingComponents.find((component) => component.id !== selectedComponent.id)?.id ?? 'hull'
      return {
        ...draftRobot,
        components: remainingComponents,
      }
    })

    setSelectedId(nextSelection)
  }

  const handleDuplicateSelected = () => {
    if (!selectedComponent || !robot) return

    const suffix = `${Date.now()}`.slice(-6)
    const duplicate: RobotComponent = {
      ...selectedComponent,
      id: `${selectedComponent.id}_copy_${suffix}`,
      name: `${selectedComponent.name} Copy`,
      position: [...selectedComponent.position],
      direction: [...selectedComponent.direction],
      transform: {
        position: [...selectedComponent.position],
        rotation: selectedComponent.transform?.rotation ?? [0, 0, 0],
      },
    }

    commitRobot((draftRobot) => ({
      ...draftRobot,
      components: [...draftRobot.components, duplicate],
    }))
    setSelectedId(duplicate.id)
  }

  const handleTransformUpdate = (position: [number, number, number], rotation: [number, number, number]) => {
    if (!selectedComponent || !robot) return

    commitRobot((draftRobot) => {
      const component = draftRobot.components.find((entry) => entry.id === selectedComponent.id)
      if (!component) return draftRobot

      component.position = [...position]
      component.rotation = [...rotation]
      component.transform = { position: [...position], rotation: [...rotation] }
      return draftRobot
    })
  }

  const updateComponent = (key: keyof RobotComponent, value: string | number | boolean | number[]) => {
    if (!selectedComponent || !robot) return

    commitRobot((draftRobot) => {
      const component = draftRobot.components.find((entry) => entry.id === selectedComponent.id)
      if (!component) return draftRobot

      const mutableComponent = component as unknown as Record<string, unknown>
      if (key === 'visible') {
        const isVisible = Boolean(value)
        mutableComponent.visible = isVisible
        const visual = (mutableComponent.visual ?? {
          enabled: isVisible,
          geometry: component.geometry ?? 'box',
          color: component.color ?? '#8ecae6',
        }) as Record<string, unknown>
        visual.enabled = isVisible
        mutableComponent.visual = visual
      }

      mutableComponent[key] = value
      return draftRobot
    })
  }

  const updateVector = (key: 'position' | 'direction', axis: 'x' | 'y' | 'z', value: number) => {
    if (!selectedComponent || !robot) return

    commitRobot((draftRobot) => {
      const component = draftRobot.components.find((entry) => entry.id === selectedComponent.id)
      if (!component) return draftRobot

      const currentVector = [...component[key]] as [number, number, number]
      currentVector[axis === 'x' ? 0 : axis === 'y' ? 1 : 2] = value
      component[key] = currentVector
      return draftRobot
    })
  }

  const updateComponentMesh = (asset: string | null) => {
    if (!selectedComponent || !robot) return

    commitRobot((draftRobot) => {
      const component = draftRobot.components.find((entry) => entry.id === selectedComponent.id)
      if (!component) return draftRobot

      const nextMesh = asset ? { asset, scale: [1, 1, 1] as [number, number, number] } : undefined
      component.mesh = nextMesh
      component.visual = {
        ...(component.visual ?? {
          enabled: component.visible,
          geometry: component.geometry ?? 'box',
          color: component.color ?? '#8ecae6',
        }),
        mesh: asset ?? null,
        enabled: component.visible,
      }
      if (asset) {
        component.geometry = component.geometry ?? 'box'
      }
      return draftRobot
    })
  }

  const getMeshAssetValue = (component: RobotComponent | null) => {
    if (!component) return ''
    const direct = component.mesh?.asset
    if (direct) return direct
    const visualMesh = component.visual?.mesh
    return typeof visualMesh === 'string' ? visualMesh : ''
  }

  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.id === selectedAssetId) ?? assets[0] ?? null,
    [assets, selectedAssetId],
  )

  const handleAssetUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.stl')) {
      setStatus('Only .stl files are supported for upload')
      event.target.value = ''
      return
    }
    if (file.size === 0) {
      setStatus('Uploaded STL file is empty')
      event.target.value = ''
      return
    }

    try {
      const { asset } = await uploadAsset(file)
      setAssets((previous) => [...previous.filter((entry) => entry.id !== asset.id), asset])
      setSelectedAssetId(asset.id)
      setStatus(`Uploaded ${asset.filename}`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to upload STL')
    } finally {
      event.target.value = ''
    }
  }

  const handleAssignAsset = () => {
    if (!selectedAsset || !selectedComponent || !robot) return

    commitRobot((draftRobot) => {
      const component = draftRobot.components.find((entry) => entry.id === selectedComponent.id)
      if (!component) return draftRobot

      component.asset_id = selectedAsset.id
      component.mesh = { asset: selectedAsset.id, scale: [1, 1, 1] }
      component.visual = {
        ...(component.visual ?? {
          enabled: component.visible,
          geometry: component.geometry ?? 'box',
          color: component.color ?? '#8ecae6',
        }),
        mesh: selectedAsset.id,
        enabled: component.visible,
      }
      if (!draftRobot.assets) {
        draftRobot.assets = []
      }
      if (!draftRobot.assets.some((asset) => asset.id === selectedAsset.id)) {
        draftRobot.assets.push({
          id: selectedAsset.id,
          name: selectedAsset.name,
          filename: selectedAsset.filename,
          path: selectedAsset.path,
          uri: selectedAsset.uri,
          type: selectedAsset.type,
          size: selectedAsset.size,
          uploaded_at: selectedAsset.uploaded_at,
        })
      }
      return draftRobot
    })

    setStatus(`Assigned ${selectedAsset.filename} to ${selectedComponent.name}`)
  }

  const handleGenerateArtifacts = async () => {
    if (!robot) return

    try {
      const artifacts = await generateRobotArtifacts(robot)
      setStatus(`Generated artifacts: ${artifacts.urdf.length} bytes URDF / ${artifacts.sdf.length} bytes SDF`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to generate artifacts')
    }
  }

  const handleDownloadURDF = async () => {
    if (!robot) return

    try {
      const artifacts = await generateRobotArtifacts(robot)
      const urdfContent = artifacts.urdf

      // Create blob and download
      const blob = new Blob([urdfContent], { type: 'application/xml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${robot.name.replace(/\s+/g, '_')}.urdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      setStatus(`Downloaded URDF: ${robot.name}.urdf`)
    } catch (error) {
      setStatus(`URDF download failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const runtimeBadge = runtimeState === 'running' ? 'RUNNING' : runtimeState === 'stopped' ? 'STOPPED' : 'IDLE'

  const handlePublishRosCommand = async () => {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
    const devTopic = '/auv/dev/cmd_vel'
    const command = {
      topic: devTopic,
      type: 'geometry_msgs/msg/Twist',
      message: {
        linear: { x: 1.0, y: 0.0, z: 0.0 },
        angular: { x: 0.0, y: 0.0, z: 0.5 },
      },
    }

    try {
      const response = await fetch(`${apiBaseUrl}/api/ros/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(command),
      })
      const payload = await response.json() as { accepted?: boolean; details?: string }
      if (!response.ok || payload.accepted !== true) {
        throw new Error(payload.details ?? 'ROS command publish failed')
      }
      setStatus(`Published dev command to ${devTopic}`)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to publish ROS command')
    }
  }

  const handleRuntimeModeChange = (nextMode: RuntimeMode) => {
    setRuntimeMode(nextMode)
    setStatus(nextMode === 'OFFLINE_PREVIEW' ? 'Offline preview mode' : nextMode === 'ROS_LIVE' ? 'ROS live mode' : 'Simulation backend mode')
    if (nextMode !== 'SIMULATION') {
      setRuntimeState('idle')
    }
  }

  const engineering = useMemo(() => {
    if (!robot) {
      return {
        configured: { mass: 0, volume: 0, cg: [0, 0, 0], cb: [0, 0, 0], fluidDensity: 0, thrust: 0, geometry: 'box' },
        calculated: { weight: 0, buoyancy: 0, netForce: 0, status: 'LOADING', cgCbRelationship: 'UNKNOWN' },
      }
    }

    const configuredMass = robot.physical.mass
    const configuredVolume = robot.physical.volume
    const configuredFluidDensity = robot.buoyancy.fluid_density
    const thrust = robot.components
      .filter((component) => component.type === 'thruster')
      .reduce((sum, component) => sum + (Number(component.max_force) || 0), 0)

    if (engineeringReport) {
      return {
        configured: {
          mass: engineeringReport.configured.mass,
          volume: engineeringReport.configured.volume,
          cg: [0, 0, 0],
          cb: [0, 0, 0],
          fluidDensity: engineeringReport.configured.fluid_density,
          thrust,
          geometry: robot.components[0]?.visual?.geometry ?? robot.components[0]?.geometry ?? 'box',
        },
        calculated: {
          weight: engineeringReport.calculated.weight,
          buoyancy: engineeringReport.calculated.buoyancy,
          netForce: engineeringReport.calculated.net_vertical_force,
          status: engineeringReport.buoyancy_status,
          cgCbRelationship: engineeringReport.calculated.net_vertical_force >= 0 ? 'CG below CB' : 'CG above CB',
        },
      }
    }

    const gravity = 9.81
    const buoyancyForce = configuredFluidDensity * configuredVolume * gravity
    const weight = configuredMass * gravity
    const netForce = buoyancyForce - weight
    const state = netForce < 0 ? 'SINKING' : netForce > 0 ? 'FLOATING' : 'NEUTRAL'

    return {
      configured: {
        mass: configuredMass,
        volume: configuredVolume,
        cg: [0, 0, 0],
        cb: [0, 0, 0],
        fluidDensity: configuredFluidDensity,
        thrust,
        geometry: robot.components[0]?.visual?.geometry ?? robot.components[0]?.geometry ?? 'box',
      },
      calculated: {
        weight,
        buoyancy: buoyancyForce,
        netForce,
        status: state,
        cgCbRelationship: netForce >= 0 ? 'CG below CB' : 'CG above CB',
      },
    }
  }, [engineeringReport, robot])

  if (!robot || showTemplateSelector) {
    return <TemplateSelector onRobotCreated={(newRobot) => {
      setRobot(newRobot)
      setShowTemplateSelector(false)
      setSelectedId(newRobot.components[0]?.id ?? 'hull')
      setHistory([cloneRobot(newRobot)])
      setHistoryIndex(0)
      setStatus('Ready')
    }} />
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-badge" />
          <span>{robot.name}</span>
        </div>

        <div className="topbar-actions">
          <button type="button" className="action-button" onClick={() => setShowTemplateSelector(true)}>
            New Robot
          </button>
          {(['OFFLINE_PREVIEW', 'ROS_LIVE', 'SIMULATION'] as RuntimeMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              className="action-button"
              style={{ opacity: runtimeMode === mode ? 1 : 0.7 }}
              onClick={() => handleRuntimeModeChange(mode)}
            >
              {mode === 'OFFLINE_PREVIEW' ? 'Offline' : mode === 'ROS_LIVE' ? 'ROS Live' : 'Simulation'}
            </button>
          ))}
          <button type="button" className="action-button" onClick={handleUndo} disabled={historyIndex <= 0}>
            Undo
          </button>
          <button type="button" className="action-button" onClick={handleRedo} disabled={historyIndex >= history.length - 1}>
            Redo
          </button>
          <button type="button" className="action-button primary" onClick={handleSave}>
            Save
          </button>
          <button type="button" className="action-button" onClick={handleGenerateArtifacts}>
            Artifacts
          </button>
          <button type="button" className="action-button" onClick={handleDownloadURDF} disabled={!robot || robot.components.length === 0}>
            Download URDF
          </button>
          <button type="button" className="action-button" onClick={handleRun}>
            Run
          </button>
          <button type="button" className="action-button" onClick={handleStop}>
            Stop
          </button>
          <button type="button" className="action-button" onClick={handleReset}>
            Reset
          </button>
        </div>
      </header>

      <aside className="left-panel">
        <div className="panel-section">
          <div className="panel-header">
            <span>Project</span>
          </div>
          <div className="status-pill">{status} · {runtimeBadge}</div>
        </div>

        <div className="panel-section">
          <div className="panel-header">
            <span>Components</span>
          </div>
          <div className="panel-actions" style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <button type="button" className="action-button" onClick={() => handleAddComponent('thruster')}>+ Add</button>
            <button type="button" className="action-button" onClick={handleDuplicateSelected}>Duplicate</button>
            <button type="button" className="action-button" onClick={handleDeleteSelected}>Delete</button>
          </div>
          <ul className="tree">
            <li className="tree-item selected">{robot.name}</li>
            {robot.components.map((component) => (
              <li
                key={component.id}
                className={`tree-item ${selectedId === component.id ? 'selected' : ''}`}
                onClick={() => setSelectedId(component.id)}
              >
                {component.name}
              </li>
            ))}
          </ul>
        </div>

        <div className="panel-section">
          <div className="panel-header">
            <span>Component Library</span>
          </div>
          <div className="field-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
            {['Hull', 'Thruster', 'Battery', 'IMU', 'Camera', 'Depth Sensor', 'Sonar', 'Controller'].map((entry) => (
              <button
                key={entry}
                type="button"
                className="action-button"
                style={{ padding: '0.4rem 0.5rem' }}
                onClick={() => handleAddComponent(entry.toLowerCase().replace(/\s+/g, '_'))}
              >
                {entry}
              </button>
            ))}
          </div>
        </div>
      </aside>

      <main className="viewer-panel">
        <div className="viewer">
          <RobotScene
            robot={robot}
            selectedId={selectedId}
            onSelect={setSelectedId}
            toolMode={toolMode}
            onTransformChange={handleTransformUpdate}
          />
        </div>
      </main>

      <aside className="right-panel">
        {selectedComponent ? (
          <>
            <div className="panel-section">
              <div className="panel-header">
                <span>Inspector</span>
              </div>
              <strong>{selectedComponent.name}</strong>
              <div className="field-grid" style={{ marginTop: '0.75rem' }}>
                {([
                  { mode: 'select', label: 'Select' },
                  { mode: 'translate', label: 'Move' },
                  { mode: 'rotate', label: 'Rotate' },
                  { mode: 'scale', label: 'Scale' },
                ] as const).map(({ mode, label }) => (
                  <button
                    key={mode}
                    type="button"
                    className="action-button"
                    style={{ opacity: toolMode === mode ? 1 : 0.7 }}
                    onClick={() => setToolMode(mode)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="field-grid">
              <div className="field">
                <label>Position X</label>
                <input
                  type="number"
                  value={selectedComponent.position[0]}
                  onChange={(event) => updateVector('position', 'x', Number(event.target.value))}
                />
              </div>
              <div className="field">
                <label>Position Y</label>
                <input
                  type="number"
                  value={selectedComponent.position[1]}
                  onChange={(event) => updateVector('position', 'y', Number(event.target.value))}
                />
              </div>
              <div className="field">
                <label>Position Z</label>
                <input
                  type="number"
                  value={selectedComponent.position[2]}
                  onChange={(event) => updateVector('position', 'z', Number(event.target.value))}
                />
              </div>

              <div className="field">
                <label>Direction X</label>
                <input
                  type="number"
                  value={selectedComponent.direction[0]}
                  onChange={(event) => updateVector('direction', 'x', Number(event.target.value))}
                />
              </div>
              <div className="field">
                <label>Direction Y</label>
                <input
                  type="number"
                  value={selectedComponent.direction[1]}
                  onChange={(event) => updateVector('direction', 'y', Number(event.target.value))}
                />
              </div>
              <div className="field">
                <label>Direction Z</label>
                <input
                  type="number"
                  value={selectedComponent.direction[2]}
                  onChange={(event) => updateVector('direction', 'z', Number(event.target.value))}
                />
              </div>

              {selectedComponent.type === 'thruster' && (
                <div className="field" style={{ gridColumn: '1 / -1' }}>
                  <label>Maximum Force</label>
                  <input
                    type="number"
                    value={selectedComponent.max_force}
                    onChange={(event) => updateComponent('max_force', Number(event.target.value))}
                    disabled={selectedComponent.locked}
                  />
                </div>
              )}

              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <label>Mesh asset</label>
                <input
                  type="text"
                  value={getMeshAssetValue(selectedComponent)}
                  onChange={(event) => updateComponentMesh(event.target.value.trim() || null)}
                  placeholder="hull.stl / leave blank for primitive"
                />
              </div>

              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <label>Upload mesh</label>
                <input
                  type="file"
                  accept=".stl,.obj,.dae,.ply"
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (!file) return
                    updateComponentMesh(file.name)
                    event.target.value = ''
                  }}
                />
              </div>
            </div>

            <div className="panel-section">
              <div className="field" style={{ gridColumn: '1 / -1' }}>
                <label>Assign selected asset</label>
                <button type="button" className="action-button" onClick={handleAssignAsset} disabled={!selectedAsset}>
                  Assign to {selectedComponent.name}
                </button>
              </div>
              <div className="checkbox-row">
                <span>Visible</span>
                <input
                  type="checkbox"
                  checked={selectedComponent.visible}
                  onChange={(event) => updateComponent('visible', event.target.checked)}
                  disabled={selectedComponent.locked}
                />
              </div>

              <div className="checkbox-row">
                <span>Locked</span>
                <input
                  type="checkbox"
                  checked={selectedComponent.locked}
                  onChange={(event) => updateComponent('locked', event.target.checked)}
                />
              </div>
            </div>
          </>
        ) : null}

        <div className="panel-section">
          <div className="panel-header">
            <span>Asset Library</span>
          </div>
          <div className="field" style={{ marginBottom: '0.6rem' }}>
            <label>Upload STL</label>
            <input type="file" accept=".stl" onChange={handleAssetUpload} />
          </div>
          {assets.length > 0 ? (
            <ul className="tree" style={{ maxHeight: 160, overflowY: 'auto' }}>
              {assets.map((asset) => (
                <li
                  key={asset.id}
                  className={`tree-item ${selectedAssetId === asset.id ? 'selected' : ''}`}
                  onClick={() => setSelectedAssetId(asset.id)}
                >
                  {asset.filename}
                </li>
              ))}
            </ul>
          ) : (
            <div className="validation-card">No STL assets uploaded yet.</div>
          )}
          {selectedAsset && <AssetPreview asset={selectedAsset} />}
        </div>

        <div className="panel-section">
          <div className="panel-header">
            <span>Runtime</span>
          </div>
          <div className="field-grid">
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <label>Runtime mode</label>
              <div className="validation-card">{runtimeMode}</div>
            </div>
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <label>ROS bridge URL</label>
              <input type="text" value={rosBridgeUrl} onChange={(event) => setRosBridgeUrl(event.target.value)} />
            </div>
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <label>ROS status</label>
              <div className="validation-card">{runtimeMode === 'ROS_LIVE' ? rosConnectionStatus : 'DISCONNECTED'}</div>
            </div>
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <label>Topics / Nodes</label>
              <div className="validation-card">{rosTopics.length > 0 ? `${rosTopics.length} topics visible` : 'No live ROS stream'}</div>
            </div>
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <button type="button" className="action-button" onClick={handlePublishRosCommand} disabled={runtimeMode !== 'ROS_LIVE'}>
                Publish dev command
              </button>
            </div>
          </div>
        </div>

        <div className="panel-section">
          <div className="panel-header">
            <span>Validation</span>
          </div>
          {issues.length > 0 ? (
            <div className="validation-card">
              {issues.map((issue) => (
                <div key={issue}>{issue}</div>
              ))}
            </div>
          ) : (
            <div className="validation-card success">Configuration valid</div>
          )}
        </div>
      </aside>

      <footer className="bottom-panel">
        <div className="telemetry-box">
          <div className="panel-header">
            <span>Engineering</span>
          </div>
          <div className="summary-row">
            <div className="summary-item">
              <strong>Configured Mass</strong>
              {engineering.configured.mass.toFixed(1)} kg
            </div>
            <div className="summary-item">
              <strong>Configured Volume</strong>
              {engineering.configured.volume.toFixed(3)} m³
            </div>
            <div className="summary-item">
              <strong>Configured Thrust</strong>
              {engineering.configured.thrust.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Calculated Weight</strong>
              {engineering.calculated.weight.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Calculated Buoyancy</strong>
              {engineering.calculated.buoyancy.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Net Force</strong>
              {engineering.calculated.netForce.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Status</strong>
              {engineering.calculated.status}
            </div>
          </div>
        </div>

        <div className="log-box">
          <div className="panel-header">
            <span>Telemetry</span>
          </div>
          <div className="summary-row">
            <div className="summary-item">
              <strong>Runtime mode</strong>
              {runtimeMode}
            </div>
            <div className="summary-item">
              <strong>Simulation</strong>
              {runtimeMode === 'SIMULATION' ? (runtimeState === 'running' ? 'RUNNING' : 'STOPPED') : 'OFFLINE'}
            </div>
            <div className="summary-item">
              <strong>Telemetry</strong>
              {runtimeMode === 'ROS_LIVE' ? rosConnectionStatus : runtimeState === 'running' ? telemetryStatus : 'DISCONNECTED'}
            </div>
            <div className="summary-item">
              <strong>Depth</strong>
              {telemetry && typeof (telemetry as any).telemetry?.depth === 'number' ? `${Number((telemetry as any).telemetry.depth).toFixed(2)} m` : 'Unavailable'}
            </div>
            <div className="summary-item">
              <strong>Pitch</strong>
              {telemetry && typeof (telemetry as any).telemetry?.imu?.pitch === 'number' ? `${Number((telemetry as any).telemetry.imu.pitch).toFixed(2)}°` : 'Unavailable'}
            </div>
            <div className="summary-item">
              <strong>ROS Topics</strong>
              {rosTopics.length}
            </div>
            <div className="summary-item">
              <strong>GZ Topics</strong>
              {telemetry && Array.isArray((telemetry as any).telemetry?.gz_topics) ? (telemetry as any).telemetry.gz_topics.length : 0}
            </div>
          </div>
          {rosTopics.length > 0 && (
            <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.5rem' }}>
              {rosTopics.slice(0, 4).map((topic) => (
                <div key={topic.topic} style={{ border: '1px solid #334155', borderRadius: 8, padding: '0.5rem' }}>
                  <div><strong>Topic:</strong> {topic.topic}</div>
                  <div><strong>Type:</strong> {topic.type}</div>
                  <div><strong>Count:</strong> {topic.count}</div>
                  <div><strong>Latest:</strong> {topic.latest ? JSON.stringify(topic.latest) : 'waiting...'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </footer>
    </div>
  )
}

export default App
