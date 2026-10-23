import { useEffect, useState } from 'react'
import { OrderFlowSteps } from '../components/OrderFlowSteps'
import { apiRequest } from '../services/api'
import type { CheckoutQuote, FulfillmentMethod, Order, PaymentMethod, User } from '../types'

type CheckoutPageProps = {
  token: string
  user: User
  schoolCity: string
  onOrderCreated: (order: Order, requiresPayment: boolean) => void
  onBackToCart: () => void
}

export function CheckoutPage({ token, user, schoolCity, onOrderCreated, onBackToCart }: CheckoutPageProps) {
  const [fulfillment, setFulfillment] = useState<FulfillmentMethod>('delivery')
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('upi')
  const [quote, setQuote] = useState<CheckoutQuote | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [deliveryArea, setDeliveryArea] = useState('')
  const [deliveryCity, setDeliveryCity] = useState(schoolCity)
  const [deliveryPostalCode, setDeliveryPostalCode] = useState('')
  const [deliveryLatitude, setDeliveryLatitude] = useState<number | null>(null)
  const [deliveryLongitude, setDeliveryLongitude] = useState<number | null>(null)
  const [locating, setLocating] = useState(false)
  const [locationMessage, setLocationMessage] = useState('')

  useEffect(() => {
    let active = true
    apiRequest<CheckoutQuote>('/checkout/quote', {
      method: 'POST',
      body: JSON.stringify({ fulfillment_method: fulfillment }),
    }, token)
      .then((data) => { if (active) setQuote(data) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Quote could not be calculated.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [fulfillment, token])

  const placeOrder = async () => {
    setSubmitting(true)
    setError('')
    try {
      const order = await apiRequest<Order>('/checkout', {
        method: 'POST',
        body: JSON.stringify({
          payment_method: paymentMethod,
          fulfillment_method: fulfillment,
          ...(fulfillment === 'delivery'
            ? {
                delivery_address: deliveryAddress.trim(),
                delivery_area: deliveryArea.trim(),
                delivery_city: (deliveryCity || schoolCity).trim(),
                delivery_postal_code: deliveryPostalCode.trim(),
                delivery_latitude: deliveryLatitude,
                delivery_longitude: deliveryLongitude,
              }
            : {}),
        }),
      }, token)
      onOrderCreated(order, paymentMethod !== 'cash')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Order could not be placed.')
    } finally {
      setSubmitting(false)
    }
  }

  const useCurrentLocation = () => {
    setLocationMessage('')
    if (!navigator.geolocation) {
      setLocationMessage('Location is not available in this browser. Enter your address below.')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setDeliveryLatitude(position.coords.latitude)
        setDeliveryLongitude(position.coords.longitude)
        setLocationMessage('Location captured. Add and confirm your street address and area below.')
        setLocating(false)
      },
      (reason) => {
        const message = reason.code === reason.PERMISSION_DENIED
          ? 'Location permission was denied. You can still enter your address manually.'
          : reason.code === reason.TIMEOUT
            ? 'Location lookup timed out. Try again or enter your address manually.'
            : 'We could not get your location. You can still enter your address manually.'
        setLocationMessage(message)
        setLocating(false)
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    )
  }

  return (
    <main className="page-container narrow-page">
      <OrderFlowSteps current="checkout" />
      <div className="page-heading compact-heading">
        <div><p className="eyebrow">Review before placing</p><h1>Checkout</h1></div>
        <button className="button button-secondary" type="button" onClick={onBackToCart}>Back to cart</button>
      </div>
      <div className="checkout-layout">
        <div className="checkout-options">
          <section className="panel form-panel">
            <h2>How would you like to receive your order?</h2>
            <div className="option-list">
              <label className="choice-card">
                <input type="radio" name="fulfillment" checked={fulfillment === 'delivery'} disabled={submitting} onChange={() => setFulfillment('delivery')} />
                <span><strong>Home delivery</strong><small>Estimated in 5 days · Delivery fee applies</small></span>
              </label>
              <label className="choice-card">
                <input type="radio" name="fulfillment" checked={fulfillment === 'pickup'} disabled={submitting} onChange={() => setFulfillment('pickup')} />
                <span><strong>Pick up at school store</strong><small>Estimated in 4 days · No delivery fee</small></span>
              </label>
            </div>
          </section>
          {fulfillment === 'delivery' && (
            <section className="panel form-panel delivery-panel">
              <div className="delivery-heading">
                <div>
                  <p className="eyebrow">DELIVERY DETAILS</p>
                  <h2>Where should we bring it?</h2>
                  <p>Choose your area and add an address. GPS is optional and only saved with this order.</p>
                </div>
                <button
                  type="button"
                  className="button button-secondary delivery-location-button"
                  disabled={locating || submitting}
                  onClick={useCurrentLocation}
                >
                  <span aria-hidden="true">◎</span> {locating ? 'Finding you…' : 'Use my location'}
                </button>
              </div>
              <div className="delivery-form-grid">
                <label className="delivery-field delivery-field-wide">Street address
                  <textarea
                    autoComplete="street-address"
                    required
                    disabled={submitting}
                    minLength={5}
                    maxLength={1000}
                    value={deliveryAddress}
                    onChange={(event) => setDeliveryAddress(event.target.value)}
                    placeholder="House / flat, building and street"
                    rows={2}
                  />
                </label>
                <label className="delivery-field">Area / neighborhood
                  <input
                    autoComplete="address-level3"
                    required
                    disabled={submitting}
                    maxLength={120}
                    value={deliveryArea}
                    onChange={(event) => setDeliveryArea(event.target.value)}
                    placeholder="Your area or locality"
                  />
                </label>
                <label className="delivery-field">City
                  <input
                    autoComplete="address-level2"
                    required
                    disabled={submitting}
                    maxLength={100}
                    value={deliveryCity || schoolCity}
                    onChange={(event) => setDeliveryCity(event.target.value)}
                    placeholder="City"
                  />
                </label>
                <label className="delivery-field delivery-field-wide">Postal code
                  <input
                    autoComplete="postal-code"
                    required
                    disabled={submitting}
                    minLength={3}
                    maxLength={20}
                    value={deliveryPostalCode}
                    onChange={(event) => setDeliveryPostalCode(event.target.value)}
                    placeholder="Postal / PIN code"
                  />
                </label>
              </div>
              {locationMessage && (
                <p className={deliveryLatitude === null ? 'delivery-location-note' : 'delivery-location-note location-success'} role="status">
                  {locationMessage}
                </p>
              )}
              {deliveryLatitude !== null && deliveryLongitude !== null && (
                <button
                  type="button"
                  className="text-button clear-location-button"
                  onClick={() => {
                    setDeliveryLatitude(null)
                    setDeliveryLongitude(null)
                    setLocationMessage('GPS coordinates removed. Your typed address will still be used.')
                  }}
                >
                  Remove GPS location
                </button>
              )}
              <p className="delivery-privacy-note">
                <strong>{user.name}</strong> · Location is optional. We only attach your selected coordinates to this delivery order.
              </p>
            </section>
          )}
          <section className="panel form-panel">
            <h2>Payment method</h2>
            <div className="option-list">
              <label className="choice-card">
                <input type="radio" name="payment" checked={paymentMethod === 'upi'} onChange={() => setPaymentMethod('upi')} />
                <span><strong>UPI</strong><small>Simulated payment result — no real money</small></span>
              </label>
              <label className="choice-card">
                <input type="radio" name="payment" checked={paymentMethod === 'net_banking'} onChange={() => setPaymentMethod('net_banking')} />
                <span><strong>Net banking</strong><small>Demo bank redirect and result</small></span>
              </label>
              <label className="choice-card">
                <input type="radio" name="payment" checked={paymentMethod === 'cash'} onChange={() => setPaymentMethod('cash')} />
                <span><strong>Cash at store</strong><small>Order stays unpaid until cashier confirmation</small></span>
              </label>
            </div>
          </section>
        </div>

        <aside className="panel order-summary">
          <h2>Order quote</h2>
          {(loading || quote?.fulfillment_method !== fulfillment) && <p className="muted">Calculating totals…</p>}
          {quote?.fulfillment_method === fulfillment && (
            <>
              <div className="quote-lines">
                {quote.lines.map((line) => <div className="quote-line" key={line.cart_item_id}><span>{line.name} · {line.size} × {line.quantity}</span><strong>₹{line.line_total.toLocaleString('en-IN')}</strong></div>)}
              </div>
              <div className="summary-row"><span>Subtotal</span><strong>₹{quote.subtotal.toLocaleString('en-IN')}</strong></div>
              <div className="summary-row"><span>Tax</span><strong>₹{quote.tax.toLocaleString('en-IN')}</strong></div>
              <div className="summary-row"><span>Delivery</span><strong>{quote.delivery_fee ? `₹${quote.delivery_fee.toLocaleString('en-IN')}` : 'Free'}</strong></div>
              <div className="summary-row summary-total"><span>Total</span><strong>₹{quote.total.toLocaleString('en-IN')}</strong></div>
              <p className="summary-note">Estimated {fulfillment === 'pickup' ? 'pickup' : 'delivery'}: {new Date(quote.estimated_ready_at).toLocaleDateString()}</p>
            </>
          )}
          {error && <p className="error-text" role="alert">{error}</p>}
          <button
            className="button button-primary button-block"
            type="button"
            disabled={
              loading
              || quote?.fulfillment_method !== fulfillment
              || submitting
              || (fulfillment === 'delivery'
                && (!deliveryAddress.trim() || !deliveryArea.trim() || !deliveryCity.trim() || !deliveryPostalCode.trim()))
            }
            onClick={() => void placeOrder()}
          >
            {submitting ? 'Placing order…' : 'Place order'}
          </button>
          <p className="summary-note">This is a proof of concept. No real payment is processed.</p>
        </aside>
      </div>
    </main>
  )
}
