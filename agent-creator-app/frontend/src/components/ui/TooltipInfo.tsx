import { useState, useRef, useEffect } from 'react'
import { HelpCircle } from 'lucide-react'

interface TooltipInfoProps {
  text: string
  title?: string
}

export function TooltipInfo({ text, title = 'O que é isso?' }: TooltipInfoProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div className="relative inline-block" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-indigo-400 hover:text-indigo-600 transition-colors ml-1 focus:outline-none"
        aria-label="O que é isso?"
      >
        <HelpCircle size={16} />
      </button>

      {open && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 animate-fade-in">
          <div className="bg-indigo-900 text-white text-sm rounded-xl p-4 shadow-xl">
            <p className="font-semibold text-indigo-200 mb-1">{title}</p>
            <p className="text-indigo-50 leading-relaxed">{text}</p>
          </div>
          {/* Arrow */}
          <div className="flex justify-center">
            <div className="w-3 h-3 bg-indigo-900 rotate-45 -mt-1.5" />
          </div>
        </div>
      )}
    </div>
  )
}
