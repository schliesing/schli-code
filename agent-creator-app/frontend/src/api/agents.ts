import client from './client'
import type { AgentConfig } from '../types/agent'

export async function createAgent(sessionId: string): Promise<AgentConfig> {
  const response = await client.post('/agents', { session_id: sessionId })
  return response.data
}

export async function getAgent(id: string): Promise<AgentConfig> {
  const response = await client.get(`/agents/${id}`)
  return response.data
}

export async function updateAgent(id: string, patch: Partial<AgentConfig>): Promise<AgentConfig> {
  const response = await client.patch(`/agents/${id}`, patch)
  return response.data
}

export async function listAgents(sessionId: string): Promise<AgentConfig[]> {
  const response = await client.get('/agents', { params: { session_id: sessionId } })
  return response.data
}

export async function deleteAgent(id: string): Promise<void> {
  await client.delete(`/agents/${id}`)
}

export async function exportAgent(token: string): Promise<Blob> {
  const response = await client.get(`/export/${token}`, { responseType: 'blob' })
  return response.data
}
