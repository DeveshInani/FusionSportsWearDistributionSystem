import { useCallback, useEffect, useState } from 'react'
import { PageHeader } from './components/PageHeader'
import { AdminDashboardPage } from './pages/AdminDashboardPage'
import { AuthPage } from './pages/AuthPage'
import { CartPage } from './pages/CartPage'
import { CatalogPage } from './pages/CatalogPage'
import { CheckoutPage } from './pages/CheckoutPage'
import { OrderConfirmationPage } from './pages/OrderConfirmationPage'
import { OrderDetailPage } from './pages/OrderDetailPage'
import { OrderHistoryPage } from './pages/OrderHistoryPage'
import { PaymentPage } from './pages/PaymentPage'
import { apiRequest } from './services/api'
import type { AuthResponse, Cart, Order, PageName, School, User } from './types'
import './App.css'

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<User | null>(null)
  const [schools, setSchools] = useState<School[]>([])
  const [cart, setCart] = useState<Cart | null>(null)
  const [page, setPage] = useState<PageName>('catalog')
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null)
  const [currentOrder, setCurrentOrder] = useState<Order | null>(null)
  const [restoringSession, setRestoringSession] = useState(Boolean(token))

  useEffect(() => {
    let active = true
    apiRequest<School[]>('/schools')
      .then((data) => { if (active) setSchools(data) })
      .catch((error: unknown) => console.error('Could not load schools', error))
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!token) {
      return
    }
    let active = true
    apiRequest<User>('/me', {}, token)
      .then((data) => {
        if (!active) return
        setUser(data)
        setPage(data.role === 'admin' ? 'admin' : 'catalog')
      })
      .catch((error: unknown) => {
        if (!active) return
        console.error('Could not restore session', error)
        localStorage.removeItem('token')
        setToken(null)
        setUser(null)
      })
      .finally(() => { if (active) setRestoringSession(false) })
    return () => { active = false }
  }, [token])

  const refreshCart = useCallback(async () => {
    if (!token || user?.role === 'admin') return
    try {
      setCart(await apiRequest<Cart>('/cart', {}, token))
    } catch (error) {
      console.error('Could not refresh cart', error)
    }
  }, [token, user?.role])

  useEffect(() => {
    if (!token || !user || user.role === 'admin') return
    let active = true
    apiRequest<Cart>('/cart', {}, token)
      .then((data) => { if (active) setCart(data) })
      .catch((error: unknown) => console.error('Could not load cart', error))
    return () => { active = false }
  }, [token, user])

  const acceptAuth = (response: AuthResponse) => {
    localStorage.setItem('token', response.access_token)
    setToken(response.access_token)
    setUser(response.user)
    setCart(null)
    setPage(response.user.role === 'admin' ? 'admin' : 'catalog')
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    setCart(null)
    setCurrentOrder(null)
    setSelectedOrderId(null)
    setRestoringSession(false)
  }

  const navigate = (next: PageName) => {
    if (!user) return
    if (user.role === 'admin' && next !== 'admin') return
    if (user.role !== 'admin' && next === 'admin') return
    setPage(next)
  }

  const startCheckout = (order: Order, requiresPayment: boolean) => {
    setCurrentOrder(order)
    setSelectedOrderId(order.id)
    setPage(requiresPayment ? 'payment' : 'confirmation')
    void refreshCart()
  }

  const studentSchool = schools.find((school) => school.id === user?.school_id)
  const schoolName = studentSchool?.name ?? ''
  const schoolCity = studentSchool?.city ?? ''
  if (restoringSession) {
    return <main className="startup-screen" aria-live="polite">Opening your school store…</main>
  }
  if (!user || !token) return <AuthPage onAuthenticated={acceptAuth} />

  let content
  if (user.role === 'admin') {
    content = <AdminDashboardPage token={token} />
  } else {
    switch (page) {
      case 'cart':
        content = (
          <CartPage
            token={token}
            onContinue={() => setPage(cart?.items.length ? 'checkout' : 'catalog')}
            onCartChanged={setCart}
          />
        )
        break
      case 'checkout':
        content = <CheckoutPage token={token} user={user} schoolCity={schoolCity} onOrderCreated={startCheckout} onBackToCart={() => setPage('cart')} />
        break
      case 'payment':
        content = currentOrder
          ? (
              <PaymentPage
                order={currentOrder}
                token={token}
                onFinished={(order) => { setCurrentOrder(order); setPage('confirmation') }}
              />
            )
          : <OrderHistoryPage token={token} onSelect={(id) => { setSelectedOrderId(id); setPage('order-detail') }} />
        break
      case 'confirmation':
        content = currentOrder
          ? (
              <OrderConfirmationPage
                order={currentOrder}
                token={token}
                onTrack={(id) => { setSelectedOrderId(id); setPage('order-detail') }}
                onShop={() => setPage('catalog')}
              />
            )
          : <OrderHistoryPage token={token} onSelect={(id) => { setSelectedOrderId(id); setPage('order-detail') }} />
        break
      case 'orders':
        content = <OrderHistoryPage token={token} onSelect={(id) => { setSelectedOrderId(id); setPage('order-detail') }} />
        break
      case 'order-detail':
        content = selectedOrderId
          ? <OrderDetailPage key={selectedOrderId} orderId={selectedOrderId} token={token} onBack={() => setPage('orders')} />
          : <OrderHistoryPage token={token} onSelect={(id) => { setSelectedOrderId(id); setPage('order-detail') }} />
        break
      default:
        content = (
          <CatalogPage
            token={token}
            user={user}
            schoolName={schoolName}
            onCartChanged={() => { void refreshCart() }}
          />
        )
    }
  }

  return (
    <div className="app-shell">
      <PageHeader
        user={user}
        schoolName={schoolName}
        cartCount={cart?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0}
        page={page}
        onNavigate={navigate}
        onLogout={logout}
      />
      {content}
      <footer className="site-footer">School uniform store · Demonstration only — payments are simulated.</footer>
    </div>
  )
}

export default App
