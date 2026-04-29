import client from './client'
import type { CatalogItem, ModelCatalogItem, SkillCatalogItem } from '../types/agent'

export async function getFrameworks(): Promise<CatalogItem[]> {
  const response = await client.get('/catalog/frameworks')
  return response.data
}

export async function getSkills(): Promise<SkillCatalogItem[]> {
  const response = await client.get('/catalog/skills')
  return response.data
}

export async function getModels(): Promise<ModelCatalogItem[]> {
  const response = await client.get('/catalog/models')
  return response.data
}

export async function getMemoryTypes(): Promise<CatalogItem[]> {
  const response = await client.get('/catalog/memory-types')
  return response.data
}

export async function getDeploymentTargets(): Promise<CatalogItem[]> {
  const response = await client.get('/catalog/deployment-targets')
  return response.data
}

export async function getRoles(): Promise<CatalogItem[]> {
  const response = await client.get('/catalog/roles')
  return response.data
}
