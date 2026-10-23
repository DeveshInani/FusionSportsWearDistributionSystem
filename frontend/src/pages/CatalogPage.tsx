import { useEffect, useMemo, useState } from 'react'
import { GuidedTour } from '../components/GuidedTour'
import { ProductCard } from '../components/ProductCard'
import { apiRequest } from '../services/api'
import type { Product, ProductVariant, User } from '../types'

type CatalogPageProps = {
  token: string
  user: User
  schoolName: string
  onCartChanged: () => void
}

export function CatalogPage({ token, user, schoolName, onCartChanged }: CatalogPageProps) {
  const [products, setProducts] = useState<Product[]>([])
  const [category, setCategory] = useState('All')
  const [gender, setGender] = useState('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const tourStorageKey = `store-tour-complete-${user.id}`
  const [tourOpen, setTourOpen] = useState(
    () => window.localStorage.getItem(tourStorageKey) !== 'complete',
  )

  useEffect(() => {
    let active = true
    apiRequest<Product[]>(`/products?school_id=${user.school_id}`, {}, token)
      .then((data) => { if (active) setProducts(data) })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Catalog could not be loaded.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, user.school_id])

  const categories = ['All', 'Uniform', 'Sportswear', 'Accessories']
  const genders = ['all', 'boys', 'girls', 'unisex']
  const visibleProducts = useMemo(() => products.filter((product) => {
    const isUniform = !product.category.toLowerCase().includes('sport') && !product.category.toLowerCase().includes('accessor')
    const categoryMatches =
      category === 'All'
      || (category === 'Uniform' && isUniform)
      || (category === 'Sportswear' && product.category.toLowerCase().includes('sport'))
      || (category === 'Accessories' && product.category.toLowerCase().includes('accessor'))
    const genderMatches = gender === 'all' || product.gender === gender || product.gender === 'unisex'
    const searchMatches = `${product.name} ${product.category} ${product.description ?? ''}`
      .toLowerCase()
      .includes(search.trim().toLowerCase())
    return categoryMatches && genderMatches && searchMatches
  }), [category, gender, products, search])

  const addToCart = async (variant: ProductVariant, quantity: number) => {
    await apiRequest('/cart/items', {
      method: 'POST',
      body: JSON.stringify({ catalog_item_id: variant.catalog_item_id, quantity }),
    }, token)
    onCartChanged()
  }

  return (
    <main className="page-container">
      <section className="catalog-hero" data-tour="collection">
        <div className="catalog-hero-copy">
          <p className="eyebrow">MADE FOR YOUR SCHOOL</p>
          <h1>Ready for every school day.</h1>
          <p>Explore the approved collection for {schoolName || 'your school'}, all in one place.</p>
          <button
            className="button button-primary catalog-hero-button"
            type="button"
            onClick={() => document.getElementById('catalog-products')?.scrollIntoView({ behavior: 'smooth' })}
          >
            Explore the collection <span aria-hidden="true">↓</span>
          </button>
        </div>
        <div className="catalog-hero-side">
          <div className="catalog-hero-stamp" aria-hidden="true">P</div>
          <div>
            <span className="catalog-student-label">SHOPPING FOR</span>
            <strong>{user.name}</strong>
            <span>Class {user.grade ?? '—'} · Section {user.section ?? '—'}</span>
          </div>
        </div>
      </section>

      <section className="catalog-discovery" id="catalog-products">
        <div className="catalog-section-heading">
          <div>
            <p className="eyebrow">THE SCHOOL EDIT</p>
            <h2>Find your everyday essentials</h2>
            <p>{loading ? 'Finding the right fit for your school…' : `${visibleProducts.length} ${visibleProducts.length === 1 ? 'style' : 'styles'} available for your school`}</p>
          </div>
          <button
            className="catalog-help-button"
            type="button"
            onClick={() => setTourOpen(true)}
            aria-label="Show the shopping guide"
          >
            <span aria-hidden="true">?</span> Shopping guide
          </button>
        </div>

        <div className="catalog-toolbar" data-tour="filters">
          <label className="catalog-search">
            <span className="sr-only">Search school products</span>
            <svg className="catalog-search-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none">
              <circle cx="10.8" cy="10.8" r="6.8" stroke="currentColor" strokeWidth="1.7" />
              <path d="m16 16 4.2 4.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search uniforms, sizes and more"
            />
            {search && (
              <button type="button" className="catalog-search-clear" onClick={() => setSearch('')} aria-label="Clear search">
                ×
              </button>
            )}
          </label>
          <div className="catalog-filters">
            <div className="category-tabs" role="tablist" aria-label="Product category">
              {categories.map((item) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={category === item}
                  className={category === item ? 'category-tab active' : 'category-tab'}
                  key={item}
                  onClick={() => setCategory(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="gender-tabs" role="group" aria-label="Uniform fit">
              {genders.map((item) => (
                <button
                  type="button"
                  aria-pressed={gender === item}
                  className={gender === item ? 'gender-tab active' : 'gender-tab'}
                  key={item}
                  onClick={() => setGender(item)}
                >
                  {item === 'all' ? 'All fits' : item[0].toUpperCase() + item.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {error && (
          <div className="catalog-empty-state" role="alert" data-tour="products">
            <span className="empty-state-icon" aria-hidden="true">!</span>
            <h3>We couldn’t load your collection</h3>
            <p>{error}</p>
            <button className="button button-secondary" type="button" onClick={() => {
              setLoading(true)
              setError('')
              apiRequest<Product[]>(`/products?school_id=${user.school_id}`, {}, token)
                .then(setProducts)
                .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Catalog could not be loaded.'))
                .finally(() => setLoading(false))
            }}>
              Try again
            </button>
          </div>
        )}
        <div className="catalog-results">
          {loading && !error && (
            <div className="product-grid" aria-label="Loading products" aria-busy="true">
              {Array.from({ length: 4 }, (_, index) => <div className="product-skeleton" data-tour={index === 0 ? 'products' : undefined} key={index} />)}
            </div>
          )}
          {!loading && !error && visibleProducts.length === 0 && (
            <div className="catalog-empty-state" data-tour="products">
              <span className="empty-state-icon" aria-hidden="true">⌕</span>
              <h3>No matching pieces just yet</h3>
              <p>Try another search or clear your filters to see the full school collection.</p>
              <button className="button button-secondary" type="button" onClick={() => {
                setSearch('')
                setCategory('All')
                setGender('all')
              }}>
                Clear all filters
              </button>
            </div>
          )}
          {!loading && !error && visibleProducts.length > 0 && (
            <section className="product-grid" aria-label="Products">
              {visibleProducts.map((product, index) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onAdd={addToCart}
                  tourTarget={index === 0 ? 'products' : undefined}
                />
              ))}
            </section>
          )}
        </div>
      </section>
      {tourOpen && (
        <GuidedTour storageKey={tourStorageKey} onComplete={() => setTourOpen(false)} />
      )}
    </main>
  )
}
