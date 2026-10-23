import { useEffect, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { apiRequest } from '../services/api'
import type { Order } from '../types'

type OrderHistoryPageProps = {
  token: string
  onSelect: (orderId: number) => void
}

export function OrderHistoryPage({ token, onSelect }: OrderHistoryPageProps) {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest<Order[]>('/orders?limit=50&offset=0', {}, token)
      .then((data) => {
        if (!active) return
        setOrders(data)
        setHasMore(data.length === 50)
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Order history could not be loaded.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token])

  const loadMore = async () => {
    setLoadingMore(true)
    setError('')
    try {
      const next = await apiRequest<Order[]>(`/orders?limit=50&offset=${orders.length}`, {}, token)
      setOrders((current) => [...current, ...next])
      setHasMore(next.length === 50)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'More orders could not be loaded.')
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <main className="page-container narrow-page">
      <div className="page-heading compact-heading"><div><p className="eyebrow">Your account</p><h1>My orders</h1></div></div>
      {loading && <p className="state-message">Loading order history…</p>}
      {error && <p className="error-text" role="alert">{error}</p>}
      {!loading && !error && orders.length === 0 && <section className="empty-panel"><h2>No orders yet</h2><p>Your order history will appear here after checkout.</p></section>}
      <div className="order-list">
        {orders.map((order) => (
          <button className="panel order-list-item" type="button" key={order.id} onClick={() => onSelect(order.id)}>
            <div>
              <span className="eyebrow">{new Date(order.created_at).toLocaleDateString()}</span>
              <h2>{order.order_number}</h2>
              <p>{order.items.length} items · {order.fulfillment_method === 'pickup' ? 'School pickup' : 'Delivery'}</p>
            </div>
            {hasMore && <button className="button button-secondary" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? 'Loading…' : 'Load more orders'}</button>}
            <div className="order-list-status"><strong>₹{order.total_amount.toLocaleString('en-IN')}</strong><StatusBadge status={order.status} /><StatusBadge status={order.payment_status} /></div>
          </button>
        ))}
      </div>
    </main>
  )
}
