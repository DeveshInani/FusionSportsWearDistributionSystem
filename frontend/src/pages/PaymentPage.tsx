import { useState } from 'react'
import { OrderFlowSteps } from '../components/OrderFlowSteps'
import { apiRequest } from '../services/api'
import type { Order } from '../types'

type PaymentPageProps = {
  order: Order
  token: string
  onFinished: (order: Order, success: boolean) => void
}

export function PaymentPage({ order, token, onFinished }: PaymentPageProps) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const isBankRedirect = order.payment_method === 'Net banking'

  const simulate = async (outcome: 'success' | 'failure') => {
    setSubmitting(true)
    setError('')
    try {
      await apiRequest(`/orders/${order.id}/payment/simulate`, {
        method: 'POST',
        body: JSON.stringify({ outcome }),
      }, token)
      const updatedOrder = await apiRequest<Order>(`/orders/${order.id}`, {}, token)
      onFinished(updatedOrder, outcome === 'success')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Payment result could not be recorded.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page-container narrow-page">
      <OrderFlowSteps current="payment" />
      <section className="panel payment-panel">
        <p className="eyebrow">{isBankRedirect ? 'Demo bank redirect' : 'UPI collect request'}</p>
        <h1>{isBankRedirect ? 'Complete net banking' : 'Confirm UPI payment'}</h1>
        <p className="muted">Order {order.order_number} · ₹{order.total_amount.toLocaleString('en-IN')}</p>
        {isBankRedirect ? (
          <div className="demo-redirect">
            <span className="demo-bank-mark">DB</span>
            <div><strong>Demo Bank</strong><span>Secure demonstration checkout</span></div>
          </div>
        ) : (
          <div className="upi-request">
            <strong>Payment request</strong>
            <span>school.store@demo</span>
            <span>Amount ₹{order.total_amount.toLocaleString('en-IN')}</span>
          </div>
        )}
        <p className="summary-note">Choose an outcome to simulate the payment gateway. No money will move.</p>
        {error && <p className="error-text" role="alert">{error}</p>}
        <div className="payment-actions">
          <button className="button button-primary" type="button" disabled={submitting} onClick={() => void simulate('success')}>Simulate successful payment</button>
          <button className="button button-secondary" type="button" disabled={submitting} onClick={() => void simulate('failure')}>Simulate declined payment</button>
        </div>
        {submitting && <p className="state-message">Recording the simulated result…</p>}
      </section>
    </main>
  )
}
