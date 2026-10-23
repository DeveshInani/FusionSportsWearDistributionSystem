import { useEffect, useState } from 'react'
import { OrderFlowSteps } from '../components/OrderFlowSteps'
import { apiRequest } from '../services/api'
import type { Cart } from '../types'

type CartPageProps = {
  token: string
  onContinue: () => void
  onCartChanged: (cart: Cart) => void
}

export function CartPage({ token, onContinue, onCartChanged }: CartPageProps) {
  const [cart, setCart] = useState<Cart | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    apiRequest<Cart>('/cart', {}, token)
      .then((data) => {
        if (active) {
          setCart(data)
          onCartChanged(data)
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Cart could not be loaded.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, onCartChanged])

  const updateQuantity = async (itemId: number, quantity: number) => {
    setError('')
    try {
      const data = await apiRequest<Cart>(`/cart/items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify({ quantity }),
      }, token)
      setCart(data)
      onCartChanged(data)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Quantity could not be updated.')
    }
  }

  const removeItem = async (itemId: number) => {
    setError('')
    try {
      const data = await apiRequest<Cart>(`/cart/items/${itemId}`, { method: 'DELETE' }, token)
      setCart(data)
      onCartChanged(data)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Item could not be removed.')
    }
  }

  if (loading) return <main className="page-container"><p className="state-message">Loading cart…</p></main>

  return (
    <main className="page-container narrow-page">
      <OrderFlowSteps current="cart" />
      <div className="page-heading compact-heading">
        <div><p className="eyebrow">Your selection</p><h1>Shopping cart</h1></div>
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
      {!cart?.items.length ? (
        <section className="empty-panel">
          <h2>Your cart is empty</h2>
          <p>Browse your school catalog and add the sizes you need.</p>
          <button className="button button-primary" type="button" onClick={onContinue}>Browse catalog</button>
        </section>
      ) : (
        <div className="cart-layout">
          <section className="panel cart-list" aria-label="Cart items">
            {cart.items.map((item) => (
              <article className="cart-line" key={item.id}>
                <div className="cart-line-title">
                  <h2>{item.product_name}</h2>
                  <p>Size {item.size}{item.color ? ` · ${item.color}` : ''}</p>
                  <span>₹{item.unit_price.toLocaleString('en-IN')} each</span>
                </div>
                <div className="cart-line-actions">
                  <label className="quantity-control">
                    <span>Quantity</span>
                    <input
                      type="number"
                      min={1}
                      max={item.stock_quantity}
                      value={item.quantity}
                      onChange={(event) => {
                        const quantity = Number(event.target.value)
                        if (quantity >= 1 && quantity <= item.stock_quantity) void updateQuantity(item.id, quantity)
                      }}
                    />
                  </label>
                  <strong>₹{item.line_total.toLocaleString('en-IN')}</strong>
                  <button className="text-button" type="button" onClick={() => void removeItem(item.id)}>Remove</button>
                </div>
              </article>
            ))}
          </section>
          <aside className="panel order-summary">
            <h2>Summary</h2>
            <div className="summary-row"><span>Subtotal</span><strong>₹{cart.total.toLocaleString('en-IN')}</strong></div>
            <p className="summary-note">Tax and delivery are calculated at checkout.</p>
            <button className="button button-primary button-block" type="button" onClick={onContinue}>Continue to checkout</button>
          </aside>
        </div>
      )}
    </main>
  )
}
