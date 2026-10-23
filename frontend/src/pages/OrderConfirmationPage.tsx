import { useEffect, useState } from 'react'
import { OrderFlowSteps } from '../components/OrderFlowSteps'
import { StatusBadge } from '../components/StatusBadge'
import { apiRequest, downloadInvoice } from '../services/api'
import type { NotificationItem, Order } from '../types'

type OrderConfirmationPageProps = {
  order: Order
  token: string
  onTrack: (orderId: number) => void
  onShop: () => void
}

export function OrderConfirmationPage({ order: initialOrder, token, onTrack, onShop }: OrderConfirmationPageProps) {
  const [order, setOrder] = useState(initialOrder)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest<Order>(`/orders/${initialOrder.id}`, {}, token)
      .then((data) => { if (active) setOrder(data) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Order details could not be refreshed.') })
    apiRequest<NotificationItem[]>('/notifications', {}, token)
      .then((data) => { if (active) setNotifications(data) })
      .catch(() => { if (active) setNotifications([]) })
    return () => { active = false }
  }, [initialOrder.id, token])

  const download = async () => {
    try {
      await downloadInvoice(order.id, token)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Invoice could not be downloaded.')
    }
  }

  const latestNotification = notifications[0]
  const success = order.payment_status === 'paid'
  const failed = order.payment_status === 'failed'
  const cashDue = order.payment_method === 'Cash at store' && order.payment_status === 'pending'
  const cancelled = order.status === 'cancelled'

  return (
    <main className="page-container narrow-page">
      <OrderFlowSteps current="complete" />
      <section className="panel confirmation-panel">
        <div className={success ? 'confirmation-icon success-icon' : 'confirmation-icon'} aria-hidden="true">{success ? '✓' : '•'}</div>
        <p className="eyebrow">{cancelled ? 'Order cancelled' : success ? 'Order confirmed' : 'Order received'}</p>
        <h1>{cancelled ? 'This order was cancelled.' : success ? 'Thank you for your order.' : failed ? 'Payment was not completed.' : cashDue ? 'Your order is saved.' : 'Payment is required.'}</h1>
        <p className="muted">
          {cancelled
            ? 'The order is cancelled and its reserved stock has been released.'
            : success
            ? 'Payment is confirmed and the school store will prepare your items.'
            : failed
              ? 'No payment was taken. Your order is still received; you can retry payment if stock is available, or cancel it from order tracking.'
              : cashDue
                ? 'Payment is due at the school store cashier. Preparation starts after the cashier confirms payment.'
                : 'Complete payment from order tracking to begin preparation.'}
        </p>

        <div className="confirmation-number">
          <span>Order number</span>
          <strong>{order.order_number}</strong>
        </div>
        <div className="confirmation-grid">
          <div><span>Payment</span><StatusBadge status={order.payment_status} /></div>
          <div><span>Fulfillment</span><strong>{order.fulfillment_method === 'pickup' ? 'School pickup' : 'Home delivery'}</strong></div>
          <div><span>Estimated {order.fulfillment_method === 'pickup' ? 'pickup' : 'delivery'}</span><strong>{new Date(order.estimated_ready_at).toLocaleDateString()}</strong></div>
          <div><span>Subtotal</span><strong>₹{order.subtotal.toLocaleString('en-IN')}</strong></div>
          <div><span>Tax</span><strong>₹{order.tax_amount.toLocaleString('en-IN')}</strong></div>
          <div><span>Delivery</span><strong>{order.delivery_fee ? `₹${order.delivery_fee.toLocaleString('en-IN')}` : 'Free'}</strong></div>
          <div><span>Order total</span><strong>₹{order.total_amount.toLocaleString('en-IN')}</strong></div>
          <div><span>Amount paid</span><strong>₹{order.amount_paid.toLocaleString('en-IN')}</strong></div>
          <div><span>Amount due</span><strong>₹{Math.max(0, order.total_amount - order.amount_paid).toLocaleString('en-IN')}</strong></div>
        </div>
        {order.fulfillment_method === 'delivery' && order.delivery_address && (
          <div className="confirmation-delivery-address">
            <span>Delivery address</span>
            <strong>{order.delivery_address}</strong>
            <span>{[order.delivery_area, order.delivery_city, order.delivery_postal_code].filter(Boolean).join(', ')}</span>
            {order.delivery_latitude !== null && order.delivery_latitude !== undefined && <small>GPS coordinates saved with this order.</small>}
          </div>
        )}

        {order.invoice_number && (
          <div className="invoice-row">
            <span>Demo invoice <strong>{order.invoice_number}</strong></span>
            <button className="button button-secondary" type="button" onClick={() => void download()}>Download PDF</button>
          </div>
        )}
        {latestNotification && (
          <div className="notification-log">
            <strong>Notification log</strong>
            <p>{latestNotification.title}: {latestNotification.body}</p>
          </div>
        )}
        {error && <p className="error-text" role="alert">{error}</p>}
        <div className="payment-actions">
          <button className="button button-primary" type="button" onClick={() => onTrack(order.id)}>Track this order</button>
          <button className="button button-secondary" type="button" onClick={onShop}>Continue shopping</button>
        </div>
      </section>
    </main>
  )
}
