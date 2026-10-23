import { useEffect, useMemo, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { apiRequest, downloadInvoice } from '../services/api'
import type { Order, Product } from '../types'

type OrderDetailPageProps = {
  orderId: number
  token: string
  onBack: () => void
}

export function OrderDetailPage({ orderId, token, onBack }: OrderDetailPageProps) {
  const [order, setOrder] = useState<Order | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [quantities, setQuantities] = useState<Record<number, number>>({})
  const [editing, setEditing] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [working, setWorking] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest<Order>(`/orders/${orderId}`, {}, token)
      .then((data) => { if (active) setOrder(data) })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Order could not be loaded.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [orderId, token])

  const availableVariants = useMemo(
    () => products.flatMap((product) => product.variants.map((variant) => ({ product, variant }))),
    [products],
  )
  const canModifyOrder = Boolean(
    order && (
      (order.status === 'awaiting_payment' && order.payment_status === 'pending')
      || (order.status === 'processing' && order.payment_status === 'paid')
    ),
  )
  const canCancelOrder = Boolean(
    order
    && ['awaiting_payment', 'processing'].includes(order.status)
    && !['cancelled', 'refunded'].includes(order.payment_status),
  )

  const startEditing = async () => {
    setError('')
    try {
      const data = await apiRequest<Product[]>('/products', {}, token)
      const nextQuantities: Record<number, number> = {}
      for (const item of order?.items ?? []) nextQuantities[item.variant_id] = item.quantity
      setProducts(data)
      setQuantities(nextQuantities)
      setEditing(true)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Catalog items could not be loaded.')
    }
  }

  const saveChanges = async () => {
    if (!order) return
    const items = availableVariants
      .filter(({ variant }) => (quantities[variant.id] ?? 0) > 0)
      .map(({ variant }) => ({
        catalog_item_id: variant.catalog_item_id,
        quantity: quantities[variant.id],
      }))
    if (!items.length) {
      setError('Keep at least one item or cancel the order.')
      return
    }
    setWorking(true)
    setError('')
    try {
      const updated = await apiRequest<Order>(`/orders/${order.id}/items`, {
        method: 'PUT',
        body: JSON.stringify({ items }),
      }, token)
      setOrder(updated)
      setEditing(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Order could not be updated.')
    } finally {
      setWorking(false)
    }
  }

  const cancelOrder = async () => {
    if (!order) return
    setWorking(true)
    setError('')
    try {
      const updated = await apiRequest<Order>(`/orders/${order.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason: cancelReason }),
      }, token)
      setOrder(updated)
      setCancelling(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Order could not be cancelled.')
    } finally {
      setWorking(false)
    }
  }

  const simulateAdjustment = async (outcome: 'success' | 'failure') => {
    if (!order) return
    setWorking(true)
    setError('')
    try {
      const result = await apiRequest<{ payment_status: string }>(`/orders/${order.id}/payment/adjustment/simulate`, {
        method: 'POST',
        body: JSON.stringify({ outcome }),
      }, token)
      const updated = await apiRequest<Order>(`/orders/${order.id}`, {}, token)
      setOrder(updated)
      if (result.payment_status === 'adjustment_failed') setError('Payment adjustment failed. The order is on hold; retry the adjustment or cancel the order.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Payment adjustment could not be recorded.')
    } finally {
      setWorking(false)
    }
  }

  const retryPayment = async (outcome: 'success' | 'failure') => {
    if (!order) return
    setWorking(true)
    setError('')
    try {
      await apiRequest(`/orders/${order.id}/payment/simulate`, {
        method: 'POST',
        body: JSON.stringify({ outcome }),
      }, token)
      const updated = await apiRequest<Order>(`/orders/${order.id}`, {}, token)
      setOrder(updated)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Payment could not be retried.')
    } finally {
      setWorking(false)
    }
  }

  const download = async () => {
    try {
      await downloadInvoice(orderId, token)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Invoice could not be downloaded.')
    }
  }

  if (loading) return <main className="page-container"><p className="state-message">Loading order details…</p></main>
  if (!order) return <main className="page-container narrow-page"><p className="error-text" role="alert">{error || 'Order not found.'}</p><button className="button button-secondary" type="button" onClick={onBack}>Back</button></main>

  return (
    <main className="page-container narrow-page">
      <div className="page-heading compact-heading">
        <div><p className="eyebrow">Order tracking</p><h1>{order.order_number}</h1></div>
        <button className="button button-secondary" type="button" onClick={onBack}>Back to orders</button>
      </div>
      <section className="panel tracking-summary">
        <div><span>Order status</span><StatusBadge status={order.status} /></div>
        <div><span>Payment</span><StatusBadge status={order.payment_status} /></div>
        <div><span>Estimated {order.fulfillment_method === 'pickup' ? 'pickup' : 'delivery'}</span><strong>{new Date(order.estimated_ready_at).toLocaleDateString()}</strong></div>
        <div><span>Total</span><strong>₹{order.total_amount.toLocaleString('en-IN')}</strong></div>
      </section>
      {order.fulfillment_method === 'delivery' && order.delivery_address && (
        <section className="panel delivery-order-card">
          <p className="eyebrow">DELIVERY ADDRESS</p>
          <strong>{order.delivery_address}</strong>
          <p>{[order.delivery_area, order.delivery_city, order.delivery_postal_code].filter(Boolean).join(', ')}</p>
          {order.delivery_latitude !== null && order.delivery_latitude !== undefined && (
            <small>GPS coordinates were shared for this delivery.</small>
          )}
        </section>
      )}
      {order.status === 'awaiting_payment' && order.payment_method !== 'Cash at store' && ['pending', 'failed'].includes(order.payment_status) && (
        <section className="panel adjustment-panel">
          <div>
            <strong>{order.payment_status === 'failed' ? 'Payment was declined' : 'Payment is due'}</strong>
            <p>Your order is received. Complete payment to start preparation. If a previous attempt failed, stock must still be available to retry.</p>
          </div>
          <div className="payment-actions">
            <button className="button button-primary" type="button" disabled={working} onClick={() => void retryPayment('success')}>Simulate payment success · ₹{order.total_amount.toLocaleString('en-IN')}</button>
            <button className="button button-secondary" type="button" disabled={working} onClick={() => void retryPayment('failure')}>Simulate declined payment</button>
          </div>
        </section>
      )}
      {order.status === 'processing' && ['adjustment_pending', 'adjustment_failed'].includes(order.payment_status) && (
        <section className="panel adjustment-panel">
          <div>
            <strong>{order.payment_status === 'adjustment_failed' ? 'Payment adjustment failed' : 'Payment adjustment required'}</strong>
            <p>
              {Math.abs(order.total_amount - order.amount_paid) > 0
                ? `${order.total_amount > order.amount_paid ? 'Additional payment due' : 'Refund due'}: ₹${Math.abs(order.total_amount - order.amount_paid).toLocaleString('en-IN')}. `
                : ''}
              The store cannot prepare this order until the adjustment is resolved. You can retry or cancel.
            </p>
          </div>
          <div className="payment-actions">
            <button className="button button-primary" type="button" disabled={working} onClick={() => void simulateAdjustment('success')}>Simulate adjustment success</button>
            <button className="button button-secondary" type="button" disabled={working} onClick={() => void simulateAdjustment('failure')}>Simulate adjustment failure</button>
          </div>
        </section>
      )}
      <div className="tracking-layout">
        <section className="panel">
          <div className="section-heading"><h2>Status timeline</h2></div>
          {order.status_history.length ? (
            <ol className="timeline">
              {order.status_history.map((entry, index) => (
                <li className="timeline-entry" key={`${entry.created_at}-${index}`}>
                  <span className="timeline-dot" />
                  <div><strong>{entry.status.replaceAll('_', ' ')}</strong><p>{entry.note}</p><time>{new Date(entry.created_at).toLocaleString()}</time></div>
                </li>
              ))}
            </ol>
          ) : <p className="muted">No status updates have been recorded.</p>}
        </section>
        <aside className="panel">
          <div className="section-heading"><h2>Items</h2>{order.invoice_number && <button className="text-button" type="button" onClick={() => void download()}>Invoice PDF</button>}</div>
          {editing ? (
            <div className="edit-order-list">
              {availableVariants.map(({ product, variant }) => {
                const currentQuantity = order.items.find((item) => item.variant_id === variant.id)?.quantity ?? 0
                const quantity = quantities[variant.id] ?? 0
                const maxQuantity = variant.stock_quantity + currentQuantity
                return (
                  <label className="edit-order-item" key={variant.id}>
                    <span><strong>{product.name} · {variant.size}</strong><small>{variant.color || 'Standard'} · {variant.stock_quantity} available</small></span>
                    <input
                      aria-label={`${product.name} size ${variant.size} quantity`}
                      type="number"
                      min={0}
                      max={maxQuantity}
                      value={quantity}
                      onChange={(event) => setQuantities((previous) => ({
                        ...previous,
                        [variant.id]: Math.max(0, Math.min(Number(event.target.value) || 0, maxQuantity)),
                      }))}
                    />
                  </label>
                )
              })}
              <div className="payment-actions">
                <button className="button button-primary" type="button" disabled={working} onClick={() => void saveChanges()}>Save order changes</button>
                <button className="button button-secondary" type="button" onClick={() => setEditing(false)}>Discard</button>
              </div>
            </div>
          ) : (
            <>
              <div className="quote-lines">
                {order.items.map((item) => <div className="quote-line" key={item.id}><span>{item.name} · {item.size} × {item.quantity}</span><strong>₹{(item.unit_price * item.quantity).toLocaleString('en-IN')}</strong></div>)}
              </div>
              <div className="summary-row"><span>Subtotal</span><strong>₹{order.subtotal.toLocaleString('en-IN')}</strong></div>
              <div className="summary-row"><span>Tax</span><strong>₹{order.tax_amount.toLocaleString('en-IN')}</strong></div>
              <div className="summary-row"><span>Delivery</span><strong>{order.delivery_fee ? `₹${order.delivery_fee.toLocaleString('en-IN')}` : 'Free'}</strong></div>
              {order.amount_paid > 0 && <div className="summary-row"><span>Paid</span><strong>₹{order.amount_paid.toLocaleString('en-IN')}</strong></div>}
              <div className="summary-row summary-total"><span>Order total</span><strong>₹{order.total_amount.toLocaleString('en-IN')}</strong></div>
            </>
          )}
          <p className="summary-note">{order.payment_method} · Payment {order.payment_status} · {order.fulfillment_method === 'pickup' ? 'School pickup' : 'Delivery'}</p>
          {(canModifyOrder || canCancelOrder) && !editing && (
            <div className="order-edit-actions">
              {canModifyOrder && <button className="button button-secondary button-small" type="button" onClick={() => void startEditing()}>Modify order</button>}
              {canCancelOrder && <button className="text-button cancel-order-button" type="button" onClick={() => setCancelling((value) => !value)}>Cancel order</button>}
            </div>
          )}
          {cancelling && (
            <div className="cancel-order-form">
              <label htmlFor="cancel-reason">Reason for cancellation</label>
              <textarea id="cancel-reason" minLength={3} maxLength={500} value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} />
              <div className="payment-actions">
                <button className="button button-primary" type="button" disabled={working || cancelReason.trim().length < 3} onClick={() => void cancelOrder()}>Confirm cancellation</button>
                <button className="button button-secondary" type="button" onClick={() => setCancelling(false)}>Keep order</button>
              </div>
            </div>
          )}
        </aside>
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
    </main>
  )
}
