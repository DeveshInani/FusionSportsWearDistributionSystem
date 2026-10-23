export function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    awaiting_payment: 'Order received · awaiting payment',
    adjustment_pending: 'Adjustment due',
    adjustment_failed: 'Adjustment failed',
    ready_for_pickup: 'Ready for pickup',
    out_for_delivery: 'Out for delivery',
  }
  const label = labels[status] ?? status.replaceAll('_', ' ')
  return <span className={`status-badge status-${status}`}>{label}</span>
}
