import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AgentConfig } from '../types/agent'

function generateSessionId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

interface AgentWizardState {
  config: Partial<AgentConfig>
  currentStep: number
  sessionId: string
  agentId: string | null
  lastSavedAt: string | null
  isDirty: boolean
  // Actions
  setStep: (step: number) => void
  updateConfig: (patch: Partial<AgentConfig>) => void
  setAgentId: (id: string | null) => void
  resetWizard: () => void
  markSaved: () => void
}

export const useAgentWizardStore = create<AgentWizardState>()(
  persist(
    (set) => ({
      config: {},
      currentStep: 0,
      sessionId: generateSessionId(),
      agentId: null,
      lastSavedAt: null,
      isDirty: false,

      setStep: (step) => set({ currentStep: step }),

      updateConfig: (patch) =>
        set((state) => ({
          config: { ...state.config, ...patch },
          isDirty: true,
        })),

      setAgentId: (id) => set({ agentId: id }),

      resetWizard: () =>
        set({
          config: {},
          currentStep: 0,
          agentId: null,
          lastSavedAt: null,
          isDirty: false,
          sessionId: generateSessionId(),
        }),

      markSaved: () =>
        set({
          lastSavedAt: new Date().toISOString(),
          isDirty: false,
        }),
    }),
    {
      name: 'agent-wizard-store',
      partialize: (state) => ({
        sessionId: state.sessionId,
        agentId: state.agentId,
        config: state.config,
        currentStep: state.currentStep,
      }),
    }
  )
)
