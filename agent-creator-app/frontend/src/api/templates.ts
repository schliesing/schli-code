import client from './client'
import type { Template } from '../types/agent'

export async function listTemplates(): Promise<Template[]> {
  const response = await client.get('/templates')
  return response.data
}

export async function getTemplate(id: string): Promise<Template> {
  const response = await client.get(`/templates/${id}`)
  return response.data
}
