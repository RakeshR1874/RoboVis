import { useEffect, useState } from 'react'
import { getRobotTemplates, createRobotFromTemplate } from '../api/client'
import type { RobotConfig } from '../types/robot'

interface TemplateSelectorProps {
  onRobotCreated: (robot: RobotConfig) => void
}

export function TemplateSelector({ onRobotCreated }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<Record<string, string> | null>(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void (async () => {
      try {
        const availableTemplates = await getRobotTemplates()
        setTemplates(availableTemplates)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load templates')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const handleTemplateSelect = async (templateName: string) => {
    setCreating(true)
    try {
      const robot = await createRobotFromTemplate(templateName)
      onRobotCreated(robot)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create robot from template')
      setCreating(false)
    }
  }

  if (loading) {
    return (
      <div className="template-selector" style={{ padding: 40 }}>
        <p>Loading templates...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="template-selector" style={{ padding: 40 }}>
        <p style={{ color: '#ef4444' }}>{error}</p>
      </div>
    )
  }

  if (!templates) {
    return (
      <div className="template-selector" style={{ padding: 40 }}>
        <p>No templates available</p>
      </div>
    )
  }

  return (
    <div className="template-selector" style={{ padding: 40, maxWidth: 600, margin: '0 auto' }}>
      <h1>Create a New Robot</h1>
      <p style={{ color: '#94a3b8', marginBottom: 30 }}>Choose a starting template or create an empty robot configuration.</p>

      <div style={{ display: 'grid', gap: 16 }}>
        {Object.entries(templates).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => handleTemplateSelect(key)}
            disabled={creating}
            style={{
              padding: 20,
              border: '1px solid #475569',
              borderRadius: 8,
              backgroundColor: '#1e293b',
              color: '#e2e8f0',
              cursor: creating ? 'not-allowed' : 'pointer',
              opacity: creating ? 0.6 : 1,
              textAlign: 'left',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              if (!creating) e.currentTarget.style.borderColor = '#64748b'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#475569'
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 14, color: '#94a3b8' }}>
              {key === 'empty' && 'Start with a blank configuration'}
              {key === 'auv_001' && 'Preconfigured 6-thruster AUV'}
              {key === 'robotic_arm' && 'Simple 3-link articulated arm'}
            </div>
          </button>
        ))}
      </div>

      {creating && (
        <div style={{ marginTop: 20, padding: 16, backgroundColor: '#0f172a', borderRadius: 8, color: '#e2e8f0' }}>
          Creating robot from template...
        </div>
      )}
    </div>
  )
}
