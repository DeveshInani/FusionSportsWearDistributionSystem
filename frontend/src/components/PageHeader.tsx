import { Brand } from './Brand'
import type { PageName, User } from '../types'

type PageHeaderProps = {
  user: User
  schoolName: string
  cartCount: number
  page: PageName
  onNavigate: (page: PageName) => void
  onLogout: () => void
}

const studentLinks: { id: PageName; label: string }[] = [
  { id: 'catalog', label: 'Shop' },
  { id: 'orders', label: 'My orders' },
]

export function PageHeader({
  user,
  schoolName,
  cartCount,
  page,
  onNavigate,
  onLogout,
}: PageHeaderProps) {
  const links = user.role === 'admin'
    ? [{ id: 'admin' as const, label: 'Store dashboard' }]
    : studentLinks

  return (
    <header className="site-header">
      <div className="header-main">
        <Brand />
        <span className="header-school">{schoolName || 'School store'}</span>
        <nav className="main-nav" aria-label="Main navigation">
          {links.map((link) => (
            <button
              key={link.id}
              type="button"
              className={page === link.id ? 'nav-link active' : 'nav-link'}
              aria-current={page === link.id ? 'page' : undefined}
              onClick={() => onNavigate(link.id)}
            >
              {link.label}
            </button>
          ))}
          {user.role !== 'admin' && (
            <button
              type="button"
              className={page === 'cart' || page === 'checkout' ? 'nav-link active' : 'nav-link'}
              data-tour="cart"
              aria-current={page === 'cart' || page === 'checkout' ? 'page' : undefined}
              aria-label={`Shopping cart, ${cartCount} ${cartCount === 1 ? 'item' : 'items'}`}
              onClick={() => onNavigate('cart')}
            >
              <svg className="cart-nav-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none">
                <path d="M4 5h2l1.7 9.1a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 1.9-1.4L21 8H7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="10" cy="19" r="1" fill="currentColor" />
                <circle cx="18" cy="19" r="1" fill="currentColor" />
              </svg>
              Cart <span className="nav-count" aria-live="polite">{cartCount}</span>
            </button>
          )}
        </nav>
      </div>
      <div className="header-account">
        <div className="account-name">
          <strong>{user.name}</strong>
          <span>{user.role === 'admin' ? 'Store administrator' : `Grade ${user.grade ?? '—'} · ${user.section ?? '—'}`}</span>
        </div>
        <button type="button" className="button button-secondary button-small" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </header>
  )
}
