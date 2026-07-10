import { ReactNode } from 'react'
import { clsx } from 'clsx'
import { Check } from 'lucide-react'

interface StepCardProps {
  children: ReactNode
  selected: boolean
  onClick: () => void
  badge?: string
  disabled?: boolean
  className?: string
}

export function StepCard({ children, selected, onClick, badge, disabled, className }: StepCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'card-selectable w-full text-left relative transition-all duration-200',
        selected && 'card-selected',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      {badge && (
        <span className="absolute top-3 right-3 badge-beginner">{badge}</span>
      )}
      {selected && (
        <span className="absolute top-3 left-3 bg-indigo-600 text-white rounded-full p-0.5">
          <Check size={12} />
        </span>
      )}
      {children}
    </button>
  )
}
