import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Info, X } from 'lucide-react'

interface InfoModalProps {
  content: string
  variant?: 'teal' | 'blue'
}

export function InfoModal({ content, variant = 'teal' }: InfoModalProps) {
  const [isOpen, setIsOpen] = useState(false)

  const handleOpen = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsOpen(true)
  }

  const handleClose = () => {
    setIsOpen(false)
  }

  // Close on escape key
  useEffect(() => {
    if (isOpen) {
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          handleClose()
        }
      }
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  const iconColorClass = 'text-gray-400 hover:text-brandRed-700'

  const modalRoot = document.getElementById('modal-root')
  if (!modalRoot) {
    return (
      <button
        type="button"
        onClick={handleOpen}
        className="inline-flex items-center justify-center w-5 h-5 flex-shrink-0 transition-all rounded hover:bg-modernTeal-50"
        aria-label="Show information"
      >
        <Info className={`w-4 h-4 ${iconColorClass}`} />
      </button>
    )
  }

  const modal = isOpen ? (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={handleClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-brandRed-50 to-modernTeal-50">
          <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${variant === 'teal' ? 'bg-modernTeal-100' : 'bg-brandRed-100'}`}>
                <Info className={`w-5 h-5 ${variant === 'teal' ? 'text-modernTeal-700' : 'text-brandRed-700'}`} />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">Information</h3>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="p-2 hover:bg-white/80 rounded-lg transition-all hover:shadow-sm group"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-gray-500 group-hover:text-gray-700" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6 overflow-y-auto max-h-[60vh]">
          <div className="prose prose-sm max-w-none">
            <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
              {content}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 bg-gray-50">
          <button
            type="button"
            onClick={handleClose}
            className="w-full py-2.5 px-4 rounded-button font-medium text-white transition-all bg-brandRed-700 hover:bg-brandRed-800 shadow-button hover:shadow-button-hover"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  ) : null

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        className="inline-flex items-center justify-center w-5 h-5 flex-shrink-0 transition-all rounded hover:bg-modernTeal-50 group"
        aria-label="Show information"
      >
        <Info className={`w-4 h-4 ${iconColorClass}`} />
      </button>
      {modal && createPortal(modal, modalRoot)}
    </>
  )
}
