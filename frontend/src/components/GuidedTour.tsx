import { useEffect, useState } from 'react'

type TourStep = {
  target: string
  title: string
  description: string
  placement: 'bottom' | 'top' | 'left'
}

const steps: TourStep[] = [
  {
    target: '[data-tour="collection"]',
    title: 'Your school, your collection',
    description: 'Everything here is approved for your school. Your class details stay close by while you shop.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="filters"]',
    title: 'Find exactly what you need',
    description: 'Search by name, then narrow the collection by category or fit.',
    placement: 'bottom',
  },
  {
    target: '[data-tour="products"]',
    title: 'Choose a size and add it',
    description: 'Check live stock, choose a quantity, and add each size to your cart. Sold-out sizes are clearly marked.',
    placement: 'top',
  },
  {
    target: '[data-tour="cart"]',
    title: 'Review before you check out',
    description: 'Your cart stays available here. At checkout you can choose delivery or school pickup and review the full total before placing an order.',
    placement: 'bottom',
  },
]

type GuidedTourProps = {
  storageKey: string
  onComplete: () => void
}

export function GuidedTour({ storageKey, onComplete }: GuidedTourProps) {
  const [stepIndex, setStepIndex] = useState(0)
  const [position, setPosition] = useState<{
    top: number
    left: number
    placement: TourStep['placement']
  } | null>(null)
  const step = steps[stepIndex]

  useEffect(() => {
    const target = document.querySelector<HTMLElement>(step.target)
    if (!target) {
      return
    }

    const bounds = target.getBoundingClientRect()
    if (bounds.top < 16 || bounds.bottom > window.innerHeight - 16) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }

    const updatePosition = () => {
      const rect = target.getBoundingClientRect()
      const tooltipWidth = Math.min(340, window.innerWidth - 32)
      const placement = window.innerWidth < 680 && step.placement === 'left'
        ? 'bottom'
        : step.placement
      const availablePlacement = placement === 'bottom' && rect.bottom + 250 > window.innerHeight
        ? 'top'
        : placement
      const left = availablePlacement === 'left'
        ? Math.max(16, rect.left - tooltipWidth - 20)
        : Math.min(
            Math.max(16, rect.left + rect.width / 2 - tooltipWidth / 2),
            window.innerWidth - tooltipWidth - 16,
          )
      const top = availablePlacement === 'top'
        ? Math.max(16, rect.top - 220)
        : rect.bottom + 18

      setPosition({ top, left, placement: availablePlacement })
    }

    const animationFrame = window.requestAnimationFrame(updatePosition)
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [step])

  const finish = () => {
    window.localStorage.setItem(storageKey, 'complete')
    onComplete()
  }

  const next = () => {
    if (stepIndex === steps.length - 1) {
      finish()
    } else {
      setStepIndex((index) => index + 1)
    }
  }

  const target = document.querySelector<HTMLElement>(step.target)
  const rect = target?.getBoundingClientRect()

  return (
    <div className="tour-layer" aria-live="polite">
      {rect && (
        <div
          className="tour-spotlight"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
          }}
          aria-hidden="true"
        />
      )}
      {position && (
        <section
          className={`tour-card tour-card-${position.placement}`}
          style={{ top: position.top, left: position.left }}
          role="dialog"
          aria-labelledby="tour-title"
          aria-describedby="tour-description"
        >
          <div className="tour-card-topline">
            <span className="tour-step-count">A QUICK TOUR · {stepIndex + 1} OF {steps.length}</span>
            <button className="tour-close" type="button" onClick={finish} aria-label="Close tour">×</button>
          </div>
          <h2 id="tour-title">{step.title}</h2>
          <p id="tour-description">{step.description}</p>
          <div className="tour-card-footer">
            <div className="tour-dots" aria-label={`Step ${stepIndex + 1} of ${steps.length}`}>
              {steps.map((item, index) => (
                <span key={item.target} className={index === stepIndex ? 'tour-dot active' : 'tour-dot'} />
              ))}
            </div>
            <div className="tour-actions">
              {stepIndex > 0 && (
                <button className="text-button" type="button" onClick={() => setStepIndex((index) => index - 1)}>
                  Back
                </button>
              )}
              <button className="button button-primary button-small" type="button" onClick={next}>
                {stepIndex === steps.length - 1 ? 'Start shopping' : 'Next'}
                {stepIndex < steps.length - 1 && <span aria-hidden="true"> →</span>}
              </button>
            </div>
          </div>
          <span className="tour-arrow" aria-hidden="true">↓</span>
        </section>
      )}
    </div>
  )
}
