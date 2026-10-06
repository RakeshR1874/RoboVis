import type { AssetRecord, EngineeringReport, RobotConfig } from '../types/robot'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') ?? ''
  const body = contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    const detail = typeof body === 'string' ? body : (body?.detail ?? body)
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  return body as T
}

export async function getRobot(): Promise<RobotConfig> {
  const response = await fetch(`${API_BASE_URL}/api/robot`)
  return parseResponse<RobotConfig>(response)
}

export async function validateRobot(robot: RobotConfig): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/robot/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(robot),
  })

  const payload = await parseResponse<{ valid: boolean; issues: string[] }>(response)
  return payload.issues
}

export async function saveRobot(robot: RobotConfig): Promise<RobotConfig> {
  const response = await fetch(`${API_BASE_URL}/api/robot`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(robot),
  })

  return parseResponse<RobotConfig>(response)
}

export async function resetRobot(): Promise<RobotConfig> {
  const response = await fetch(`${API_BASE_URL}/api/robot/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })

  return parseResponse<RobotConfig>(response)
}

export async function getRobotTemplates(): Promise<Record<string, string>> {
  const response = await fetch(`${API_BASE_URL}/api/robot/templates`)
  const payload = await parseResponse<{ templates: Record<string, string> }>(response)
  return payload.templates
}

export async function createRobotFromTemplate(template: string): Promise<RobotConfig> {
  const response = await fetch(`${API_BASE_URL}/api/robot/from-template`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template }),
  })

  return parseResponse<RobotConfig>(response)
}

export async function getRobotEngineering(): Promise<EngineeringReport> {
  const response = await fetch(`${API_BASE_URL}/api/robot/engineering`)
  const payload = await parseResponse<{ report: EngineeringReport }>(response)
  return payload.report
}

export async function getRobotArtifacts(): Promise<{ sdf: string; urdf: string }> {
  const response = await fetch(`${API_BASE_URL}/api/robot/artifacts`)
  return parseResponse<{ sdf: string; urdf: string }>(response)
}

export async function generateRobotArtifacts(robot: RobotConfig): Promise<{ sdf: string; urdf: string }> {
  const response = await fetch(`${API_BASE_URL}/api/robot/artifacts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(robot),
  })
  return parseResponse<{ sdf: string; urdf: string }>(response)
}

export async function uploadAsset(file: File): Promise<{ asset: AssetRecord }> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/api/assets/upload`, {
    method: 'POST',
    body: formData,
  })

  return parseResponse<{ asset: AssetRecord }>(response)
}

export async function getAssets(): Promise<AssetRecord[]> {
  const response = await fetch(`${API_BASE_URL}/api/assets`)
  const payload = await parseResponse<{ assets: AssetRecord[] }>(response)
  return payload.assets
}

export async function deleteAsset(assetId: string): Promise<{ deleted: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/assets/${assetId}`, {
    method: 'DELETE',
  })
  return parseResponse<{ deleted: string; message: string }>(response)
}

export async function getSimulationStatus(): Promise<{ status: string; pid?: number; details?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/simulation/status`)
  return parseResponse<{ status: string; pid?: number; details?: string }>(response)
}

export async function runSimulation(): Promise<{ status: string; pid?: number; details?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/simulation/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  return parseResponse<{ status: string; pid?: number; details?: string }>(response)
}

export async function stopSimulation(): Promise<{ status: string; pid?: number; details?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/simulation/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  return parseResponse<{ status: string; pid?: number; details?: string }>(response)
}

export async function resetSimulation(): Promise<{ status: string; pid?: number; details?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/simulation/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  return parseResponse<{ status: string; pid?: number; details?: string }>(response)
}
