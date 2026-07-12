import { useEffect, useRef } from 'react'

/**
 * Reusable Modal Component
 * - Closes on ESC key
 * - Closes on clicking outside
 * - Smooth animations
 */
export default function Modal({ isOpen, onClose, children, title, size = 'md' }) {
    const overlayRef = useRef(null)
    const contentRef = useRef(null)

    // Handle ESC key
    useEffect(() => {
        if (!isOpen) return

        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                onClose()
            }
        }

        document.addEventListener('keydown', handleKeyDown)
        document.body.style.overflow = 'hidden' // Prevent background scroll

        return () => {
            document.removeEventListener('keydown', handleKeyDown)
            document.body.style.overflow = ''
        }
    }, [isOpen, onClose])

    // Handle click outside
    const handleOverlayClick = (e) => {
        if (e.target === overlayRef.current) {
            onClose()
        }
    }

    if (!isOpen) return null

    const sizeClasses = {
        sm: 'max-w-sm',
        md: 'max-w-md',
        lg: 'max-w-lg',
        xl: 'max-w-xl',
        full: 'max-w-4xl',
    }

    return (
        <div
            ref={overlayRef}
            onClick={handleOverlayClick}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in"
        >
            <div
                ref={contentRef}
                className={`glass-card rounded-2xl w-full ${sizeClasses[size]} animate-slide-in overflow-hidden`}
            >
                {/* Header */}
                {title && (
                    <div className="flex items-center justify-between p-5 border-b border-white/[0.03]">
                        <h2 className="text-lg font-semibold text-white">{title}</h2>
                        <button
                            onClick={onClose}
                            className="w-8 h-8 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] flex items-center justify-center text-zinc-400 hover:text-white transition-colors"
                        >
                            ✕
                        </button>
                    </div>
                )}

                {/* Content */}
                <div className="p-5">
                    {children}
                </div>
            </div>
        </div>
    )
}
