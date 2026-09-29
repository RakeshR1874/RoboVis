import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { getRobot, getRobotEngineering, resetRobot, saveRobot, validateRobot } from './api/client'
import { RobotScene } from './components/RobotScene'
import type { EngineeringReport, RobotComponent, RobotConfig } from './types/robot'

const cloneRobot = (robot: RobotConfig): RobotConfig => JSON.parse(JSON.stringify(robot))

function App() {
  const [robot, setRobot] = useState<RobotConfig | null>(null)
  const [selectedId, setSelectedId] = useState('hull')
  const [history, setHistory] = useState<RobotConfig[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [issues, setIssues] = useState<string[]>([])
  const [status, setStatus] = useState('Loading robot...')
  const [runtimeState, setRuntimeState] = useState<'idle' | 'running' | 'stopped'>('idle')
  const [engineeringReport, setEngineeringReport] = useState<EngineeringReport | null>(null)
  const [toolMode, setToolMode] = useState<'select' | 'translate' | 'rotate' | 'scale'>('select')

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

    setIssues([])
    setRuntimeState('running')
    setStatus('Simulation running')
  }

  const handleStop = () => {
    setRuntimeState('stopped')
    setStatus('Simulation stopped')
  }

  const handleReset = async () => {
    try {
      const freshRobot = await resetRobot()
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

  const runtimeBadge = runtimeState === 'running' ? 'RUNNING' : runtimeState === 'stopped' ? 'STOPPED' : 'IDLE'

  const engineering = useMemo(() => {
    if (!robot) {
      return { mass: 0, weight: 0, buoyancy: 0, netForce: 0, status: 'LOADING' }
    }

    if (engineeringReport) {
      return {
        mass: engineeringReport.configured.mass,
        weight: engineeringReport.calculated.weight,
        buoyancy: engineeringReport.calculated.buoyancy,
        netForce: engineeringReport.calculated.net_vertical_force,
        status: engineeringReport.buoyancy_status,
      }
    }

    const gravity = 9.81
    const mass = robot.physical.mass
    const volume = robot.physical.volume
    const buoyancyForce = robot.buoyancy.fluid_density * volume * gravity
    const weight = mass * gravity
    const netForce = buoyancyForce - weight
    const state = netForce < 0 ? 'SINKING' : netForce > 0 ? 'FLOATING' : 'NEUTRAL'

    return {
      mass,
      weight,
      buoyancy: buoyancyForce,
      netForce,
      status: state,
    }
  }, [engineeringReport, robot])

  if (!robot) {
    return <div className="loading-state">Loading AUV workspace…</div>
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-badge" />
          <span>{robot.name}</span>
        </div>

        <div className="topbar-actions">
          <button type="button" className="action-button" onClick={handleUndo} disabled={historyIndex <= 0}>
            Undo
          </button>
          <button type="button" className="action-button" onClick={handleRedo} disabled={historyIndex >= history.length - 1}>
            Redo
          </button>
          <button type="button" className="action-button primary" onClick={handleSave}>
            Save
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
            </div>

            <div className="panel-section">
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
              <strong>Mass</strong>
              {engineering.mass.toFixed(1)} kg
            </div>
            <div className="summary-item">
              <strong>Weight</strong>
              {engineering.weight.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Buoyancy</strong>
              {engineering.buoyancy.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Net Force</strong>
              {engineering.netForce.toFixed(1)} N
            </div>
            <div className="summary-item">
              <strong>Status</strong>
              {engineering.status}
            </div>
          </div>
        </div>

        <div className="log-box">
          <div className="panel-header">
            <span>Telemetry</span>
          </div>
          <div className="summary-row">
            <div className="summary-item">
              <strong>Depth</strong>
              0.00 m
            </div>
            <div className="summary-item">
              <strong>Pitch</strong>
              0.0°
            </div>
            <div className="summary-item">
              <strong>Roll</strong>
              0.0°
            </div>
            <div className="summary-item">
              <strong>Velocity</strong>
              0.00 m/s
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
