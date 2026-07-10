import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { WizardShell } from '../components/wizard/WizardShell'
import { StepFramework } from '../components/wizard/StepFramework'
import { StepCharacteristics } from '../components/wizard/StepCharacteristics'
import { StepSkills } from '../components/wizard/StepSkills'
import { StepModel } from '../components/wizard/StepModel'
import { StepMemory } from '../components/wizard/StepMemory'
import { StepPersonality } from '../components/wizard/StepPersonality'
import { StepDeployment } from '../components/wizard/StepDeployment'
import { StepReview } from '../components/wizard/StepReview'
import { useAgentWizardStore } from '../store/agentWizardStore'
import { createAgent, getAgent, updateAgent } from '../api/agents'
import { useAutoSave } from '../hooks/useAutoSave'

const TOTAL_STEPS = 8

export default function WizardPage() {
  const { agentId: paramAgentId } = useParams<{ agentId?: string }>()
  const { currentStep, sessionId, agentId, config, setStep, setAgentId, lastSavedAt } =
    useAgentWizardStore()
  const [isLoading, setIsLoading] = useState(false)
  const [initialized, setInitialized] = useState(false)

  // Enable auto-save
  useAutoSave()

  // Initialize: load or create agent
  useEffect(() => {
    async function init() {
      setIsLoading(true)
      try {
        if (paramAgentId && paramAgentId !== agentId) {
          // Load existing agent
          const agent = await getAgent(paramAgentId)
          setAgentId(agent.id ?? paramAgentId)
          useAgentWizardStore.getState().updateConfig(agent)
        } else if (!agentId) {
          // Create new agent
          const agent = await createAgent(sessionId)
          setAgentId(agent.id ?? null)
        }
      } catch (err) {
        console.error('Failed to initialize agent:', err)
        // Create a new one if loading failed
        if (!agentId) {
          try {
            const agent = await createAgent(sessionId)
            setAgentId(agent.id ?? null)
          } catch {
            // Continue without backend agent
          }
        }
      } finally {
        setIsLoading(false)
        setInitialized(true)
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleNext() {
    if (currentStep < TOTAL_STEPS - 1) {
      // Save on step change
      if (agentId && Object.keys(config).length > 0) {
        try {
          await updateAgent(agentId, config)
        } catch {
          // Continue even if save fails
        }
      }
      setStep(currentStep + 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  function handleBack() {
    if (currentStep > 0) {
      setStep(currentStep - 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const STEP_COMPONENTS = [
    <StepFramework key="framework" />,
    <StepCharacteristics key="characteristics" />,
    <StepSkills key="skills" />,
    <StepModel key="model" />,
    <StepMemory key="memory" />,
    <StepPersonality key="personality" />,
    <StepDeployment key="deployment" />,
    <StepReview key="review" />,
  ]

  if (!initialized && isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-bounce-slow">🤖</div>
          <p className="text-gray-600 font-medium">Preparando seu wizard...</p>
        </div>
      </div>
    )
  }

  return (
    <WizardShell
      onNext={handleNext}
      onBack={handleBack}
      isLastStep={currentStep === TOTAL_STEPS - 1}
      isLoading={isLoading}
      lastSavedAt={lastSavedAt}
    >
      {STEP_COMPONENTS[currentStep]}
    </WizardShell>
  )
}
