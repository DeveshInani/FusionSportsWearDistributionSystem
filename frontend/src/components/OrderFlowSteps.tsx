export type OrderFlowStage = 'cart' | 'checkout' | 'payment' | 'complete'

const steps: { id: OrderFlowStage; label: string }[] = [
  { id: 'cart', label: 'Your bag' },
  { id: 'checkout', label: 'Delivery & review' },
  { id: 'payment', label: 'Payment' },
  { id: 'complete', label: 'Confirmation' },
]

type OrderFlowStepsProps = {
  current: OrderFlowStage
}

export function OrderFlowSteps({ current }: OrderFlowStepsProps) {
  const currentIndex = steps.findIndex((step) => step.id === current)

  return (
    <nav className="order-flow-steps" aria-label="Order progress">
      {steps.map((step, index) => (
        <div
          className={[
            'order-flow-step',
            index < currentIndex ? 'is-complete' : '',
            index === currentIndex ? 'is-current' : '',
          ].filter(Boolean).join(' ')}
          key={step.id}
          aria-current={index === currentIndex ? 'step' : undefined}
        >
          <span className="order-flow-marker" aria-hidden="true">
            {index < currentIndex ? '✓' : String(index + 1)}
          </span>
          <span>{step.label}</span>
        </div>
      ))}
    </nav>
  )
}
