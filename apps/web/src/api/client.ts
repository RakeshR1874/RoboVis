import type { EngineeringReport, RobotConfig } from '../types/robot'

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

export async function getRobotEngineering(): Promise<EngineeringReport> {
  const response = await fetch(`${API_BASE_URL}/api/robot/engineering`)
  const payload = await parseResponse<{ report: EngineeringReport }>(response)
  return payload.report
}
