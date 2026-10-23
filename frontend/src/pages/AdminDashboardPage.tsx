import { useCallback, useEffect, useState } from 'react'
import { BarChart, LineChart } from '../components/AnalyticsCharts'
import { StatusBadge } from '../components/StatusBadge'
import { AdminSchoolsPage } from './AdminSchoolsPage'
import { apiRequest, downloadAdminInvoice } from '../services/api'
import type { AdminAnalytics, AdminOverview, EmailLog, Order, SystemHealth } from '../types'

type AdminDashboardPageProps = {
  token: string
}

type AdminTab = 'orders' | 'sales' | 'system' | 'emails' | 'schools'

const nextStatuses: Record<string, string[]> = {
  processing: ['preparing'],
  preparing: ['ready_for_pickup', 'out_for_delivery'],
  ready_for_pickup: ['picked_up'],
  out_for_delivery: ['delivered'],
}

export function AdminDashboardPage({ token }: AdminDashboardPageProps) {
  const [tab, setTab] = useState<AdminTab>('orders')
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [analytics, setAnalytics] = useState<AdminAnalytics | null>(null)
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [emails, setEmails] = useState<EmailLog[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [hasMoreOrders, setHasMoreOrders] = useState(false)
  const [loadingMoreOrders, setLoadingMoreOrders] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [workingOrder, setWorkingOrder] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    setError('')
    try {
      const [overviewData, orderData, analyticsData, emailData] = await Promise.all([
        apiRequest<AdminOverview>('/admin/overview', {}, token),
        apiRequest<Order[]>('/admin/orders?limit=100&offset=0', {}, token),
        apiRequest<AdminAnalytics>('/admin/analytics', {}, token),
        apiRequest<EmailLog[]>('/admin/email-logs', {}, token),
      ])
      setOverview(overviewData)
      setOrders(orderData)
      setHasMoreOrders(orderData.length === 100)
      setAnalytics(analyticsData)
      setEmails(emailData)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Store dashboard could not be loaded.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    let active = true
    Promise.all([
      apiRequest<AdminOverview>('/admin/overview', {}, token),
      apiRequest<Order[]>('/admin/orders?limit=100&offset=0', {}, token),
      apiRequest<AdminAnalytics>('/admin/analytics', {}, token),
      apiRequest<EmailLog[]>('/admin/email-logs', {}, token),
    ])
      .then(([overviewData, orderData, analyticsData, emailData]) => {
        if (!active) return
        setOverview(overviewData)
        setOrders(orderData)
        setHasMoreOrders(orderData.length === 100)
        setAnalytics(analyticsData)
        setEmails(emailData)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Store dashboard could not be loaded.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token])

  const loadMoreOrders = async () => {
    setLoadingMoreOrders(true)
    setError('')
    try {
      const next = await apiRequest<Order[]>(`/admin/orders?limit=100&offset=${orders.length}`, {}, token)
      setOrders((current) => [...current, ...next])
      setHasMoreOrders(next.length === 100)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'More orders could not be loaded.')
    } finally {
      setLoadingMoreOrders(false)
    }
  }

  useEffect(() => {
    if (tab !== 'system') return
    let active = true
    const loadHealth = async () => {
      try {
        const data = await apiRequest<SystemHealth>('/admin/system-health', {}, token)
        if (active) setHealth(data)
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : 'System health could not be loaded.')
      }
    }
    void loadHealth()
    const timer = window.setInterval(() => { void loadHealth() }, 5000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [tab, token])

  const changeStatus = async (order: Order, nextStatus: string) => {
    setWorkingOrder(order.id)
    setError('')
    try {
      await apiRequest(`/admin/orders/${order.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      }, token)
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Order status could not be updated.')
    } finally {
      setWorkingOrder(null)
    }
  }

  const confirmCash = async (order: Order) => {
    setWorkingOrder(order.id)
    setError('')
    try {
      await apiRequest(`/admin/orders/${order.id}/cash-payment`, { method: 'POST' }, token)
      await refresh()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Cash payment could not be confirmed.')
    } finally {
      setWorkingOrder(null)
    }
  }

  const downloadInvoice = async (order: Order) => {
    setError('')
    try {
      await downloadAdminInvoice(order.id, token)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Invoice could not be downloaded.')
    }
  }

  return (
    <main className="page-container">
      <div className="page-heading compact-heading">
        <div>
          <p className="eyebrow">Store operations</p>
          <h1>Admin dashboard</h1>
          <p>Orders, sales analytics and service health.</p>
        </div>
        <button className="button button-secondary" type="button" onClick={() => void refresh()}>Refresh data</button>
      </div>

      <nav className="admin-tabs" aria-label="Admin dashboard sections">
        {([
          ['orders', 'Orders'],
          ['sales', 'Sales analytics'],
          ['system', 'System health'],
          ['emails', 'Email log'],
          ['schools', 'Schools & catalog'],
        ] as const).map(([id, label]) => (
          <button type="button" key={id} className={tab === id ? 'admin-tab active' : 'admin-tab'} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </nav>

      {error && <p className="error-text" role="alert">{error}</p>}
      {loading ? <p className="state-message">Loading store data…</p> : (
        <>
          {tab === 'orders' && (
            <>
              {overview && (
                <section className="metric-grid" aria-label="Store summary">
                  <div className="panel metric-card"><span>Total orders</span><strong>{overview.orders}</strong></div>
                  <div className="panel metric-card"><span>Paid revenue</span><strong>₹{overview.revenue.toLocaleString('en-IN')}</strong></div>
                  <div className="panel metric-card"><span>Payments pending</span><strong>{overview.pending_orders}</strong></div>
                  <div className="panel metric-card"><span>Schools</span><strong>{overview.schools}</strong></div>
                </section>
              )}
              <section className="panel admin-order-panel">
                <div className="section-heading"><h2>Recent orders</h2><span>{orders.length} records</span></div>
                {!orders.length ? <p className="muted">No store orders yet.</p> : (
                  <div className="admin-order-list">
                    {orders.map((order) => {
                      const allowed = order.status === 'preparing'
                        ? [order.fulfillment_method === 'pickup' ? 'ready_for_pickup' : 'out_for_delivery']
                        : nextStatuses[order.status] ?? []
                      return (
                        <article className="admin-order-row" key={order.id}>
                          <div className="admin-order-main">
                            <strong>{order.order_number}</strong>
                            <span>{order.items.length} items · {order.payment_method} · {new Date(order.created_at).toLocaleDateString()}</span>
                            {order.fulfillment_method === 'delivery' && order.delivery_address && (
                              <span className="admin-shipping-address">
                                Ship to: {order.delivery_address}, {[order.delivery_area, order.delivery_city, order.delivery_postal_code].filter(Boolean).join(', ')}
                              </span>
                            )}
                          </div>
                          <div className="admin-order-total">
                            <strong>₹{order.total_amount.toLocaleString('en-IN')}</strong>
                            <StatusBadge status={order.payment_status} />
                          </div>
                          <div className="admin-order-status"><StatusBadge status={order.status} /></div>
                          <div className="admin-order-actions">
                            {order.payment_method === 'Cash at store' && order.payment_status === 'pending' && (
                              <button className="button button-secondary button-small" type="button" disabled={workingOrder === order.id} onClick={() => void confirmCash(order)}>Confirm cash</button>
                            )}
                            <button className="button button-secondary button-small" type="button" onClick={() => void downloadInvoice(order)}>Invoice PDF</button>
                            <label className="sr-only" htmlFor={`status-${order.id}`}>Update status for {order.order_number}</label>
                            <select
                              id={`status-${order.id}`}
                              className="admin-status-select"
                              value=""
                              disabled={!allowed.length || workingOrder === order.id || order.payment_status !== 'paid'}
                              onChange={(event) => { if (event.target.value) void changeStatus(order, event.target.value) }}
                            >
                              <option value="">Update status…</option>
                              {allowed.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}
                            </select>
                          </div>
                        </article>
                      )
                    })}
                  </div>
                )}
                {hasMoreOrders && <button className="button button-secondary" type="button" disabled={loadingMoreOrders} onClick={() => void loadMoreOrders()}>{loadingMoreOrders ? 'Loading…' : 'Load more orders'}</button>}
              </section>
            </>
          )}

          {tab === 'sales' && analytics && (
            <div className="analytics-layout">
              <div className="chart-wide"><LineChart title="Orders per day · last 14 days" data={analytics.daily_orders} /></div>
              <BarChart title="Units by category" data={analytics.category_sales.map((item) => ({ label: item.category, value: item.units_sold }))} />
              <BarChart title="Units by fit" data={analytics.gender_sales.map((item) => ({ label: item.gender, value: item.units_sold }))} />
              <BarChart title="Order status distribution" data={analytics.order_statuses.map((item) => ({ label: item.status.replaceAll('_', ' '), value: item.count }))} />
              <section className="panel ranking-panel">
                <h2>Most ordered products</h2>
                <ProductRanking products={analytics.top_products} />
              </section>
              <section className="panel ranking-panel">
                <h2>Least ordered products</h2>
                <ProductRanking products={analytics.slow_products} />
              </section>
            </div>
          )}

          {tab === 'system' && (
            <section className="system-section">
              <div className="system-heading">
                <div><h2>Live process health</h2><p>Sampled every 5 seconds · last sample {health ? new Date(health.sampled_at).toLocaleTimeString() : 'pending'}</p></div>
                <span className="live-indicator"><i /> Live</span>
              </div>
              <div className="metric-grid">
                <HealthMetric label="Backend RAM (RSS)" value={health ? `${health.process_rss_mb} MB` : '—'} detail="Memory used by this API process" />
                <HealthMetric label="Virtual memory" value={health ? `${health.process_vms_mb} MB` : '—'} detail="Address space reserved by the process" />
                <HealthMetric label="Backend CPU" value={health ? `${health.process_cpu_percent}%` : '—'} detail="CPU used by this API process" />
                <HealthMetric label="System memory" value={health ? `${health.system_memory_percent}%` : '—'} detail="Host-wide memory pressure" />
                <HealthMetric label="Active requests" value={health ? `${health.active_requests}` : '—'} detail="Requests currently being handled" />
                <HealthMetric label="Peak concurrency" value={health ? `${health.peak_concurrent_requests}` : '—'} detail="Since this backend process started" />
                <HealthMetric label="Requests / minute" value={health ? `${health.requests_last_minute}` : '—'} detail="Rolling 60-second count" />
                <HealthMetric label="Average latency" value={health ? `${health.average_latency_ms} ms` : '—'} detail={`P95 ${health?.p95_latency_ms ?? '—'} ms`} />
                <HealthMetric label="Backend threads" value={health ? `${health.process_threads}` : '—'} detail="Current process thread count" />
              </div>
              <p className="system-disclaimer">These are process-level, in-memory demo metrics. They reset when the API restarts and do not represent multi-worker or historical production monitoring.</p>
            </section>
          )}

          {tab === 'emails' && (
            <section className="panel email-panel">
              <div className="section-heading"><h2>Order email activity</h2><span>Latest {emails.length}</span></div>
              <p className="summary-note">Configure SMTP in the backend environment for delivery. Without SMTP, messages are recorded as simulated.</p>
              {!emails.length ? <p className="muted">No order emails have been generated.</p> : (
                <div className="email-log-list">
                  {emails.map((email) => (
                    <article className="email-log-row" key={email.id}>
                      <div><strong>{email.subject}</strong><span>{email.recipient} · {email.event_type.replaceAll('_', ' ')} · {new Date(email.created_at).toLocaleString()}</span>{email.error_message && <small className="email-error">{email.error_message}</small>}</div>
                      <StatusBadge status={email.status} />
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          {tab === 'schools' && <AdminSchoolsPage token={token} />}
        </>
      )}
    </main>
  )
}

function ProductRanking({ products }: { products: AdminAnalytics['top_products'] }) {
  if (!products.length) return <p className="muted">No completed order items to rank yet.</p>
  return (
    <div className="ranking-list">
      {products.map((product, index) => (
        <div className="ranking-row" key={`${product.name}-${product.gender}`}>
          <span className="ranking-index">{index + 1}</span>
          <div><strong>{product.name}</strong><span>{product.category} · {product.gender} · {product.order_count} orders</span></div>
          <div className="ranking-value"><strong>{product.units_sold}</strong><span>units</span></div>
        </div>
      ))}
    </div>
  )
}

function HealthMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="panel metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
}
