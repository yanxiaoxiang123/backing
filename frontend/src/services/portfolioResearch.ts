import api from './api'
import type {
  PortfolioExperiment,
  PortfolioExperimentSummary,
  PortfolioResearchRequest,
} from '../types/portfolioResearch'

export async function runPortfolioResearch(
  request: PortfolioResearchRequest,
): Promise<PortfolioExperiment> {
  return (await api.post<PortfolioExperiment>('/portfolio-research', request)).data
}

export async function listPortfolioExperiments(
  page: number,
): Promise<{ total: number; items: PortfolioExperimentSummary[] }> {
  return (
    await api.get('/portfolio-research', {
      params: { offset: (page - 1) * 20, limit: 20 },
    })
  ).data
}

export async function getPortfolioExperiment(id: string): Promise<PortfolioExperiment> {
  return (await api.get<PortfolioExperiment>(`/portfolio-research/${id}`)).data
}

export async function replayPortfolioExperiment(
  id: string,
): Promise<{ reproduced: boolean }> {
  return (await api.post(`/portfolio-research/${id}/replay`)).data
}

export async function exportPortfolioExperiment(id: string): Promise<void> {
  const response = await api.get(`/portfolio-research/${id}/export`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `portfolio-${id}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}
