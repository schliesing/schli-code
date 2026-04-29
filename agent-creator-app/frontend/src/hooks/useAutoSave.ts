import { useEffect, useRef } from 'react'
import { useAgentWizardStore } from '../store/agentWizardStore'
import { updateAgent } from '../api/agents'

const DEBOUNCE_MS = 500

export function useAutoSave() {
  const { config, agentId, isDirty, markSaved } = useAgentWizardStore()
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isSavingRef = useRef(false)

  useEffect(() => {
    if (!isDirty || !agentId) return

    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }

    timerRef.current = setTimeout(async () => {
      if (isSavingRef.current) return
      isSavingRef.current = true
      try {
        await updateAgent(agentId, config)
        markSaved()
      } catch (err) {
        console.error('Auto-save failed:', err)
      } finally {
        isSavingRef.current = false
      }
    }, DEBOUNCE_MS)

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [config, agentId, isDirty, markSaved])
}
