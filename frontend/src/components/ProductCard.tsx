import { useState } from 'react'
import { apiUrl } from '../services/api'
import type { Product, ProductVariant } from '../types'

type ProductCardProps = {
  product: Product
  onAdd: (variant: ProductVariant, quantity: number) => Promise<void>
  tourTarget?: string
}

export function ProductCard({ product, onAdd, tourTarget }: ProductCardProps) {
  const [quantities, setQuantities] = useState<Record<number, number>>({})
  const [addingVariant, setAddingVariant] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [imageFailed, setImageFailed] = useState(false)
  const stock = product.variants.reduce((sum, variant) => sum + variant.stock_quantity, 0)

  const addVariant = async (variant: ProductVariant) => {
    setAddingVariant(variant.id)
    setMessage('')
    try {
      await onAdd(variant, quantities[variant.id] ?? 1)
      setMessage('Added to cart')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not add this item.')
    } finally {
      setAddingVariant(null)
    }
  }

  return (
    <article className="product-card" data-tour={tourTarget}>
      <div className="product-image-frame">
        {product.image_url && !imageFailed ? (
          <img
            className="product-image"
            src={apiUrl(product.image_url)}
            alt={product.name}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="product-image-placeholder" aria-hidden="true">
            <span className="product-placeholder-mark">P</span>
            <span>{product.name}</span>
          </div>
        )}
        <span className="product-image-category">{product.category}</span>
      </div>
      <div className="product-content">
        <div className="product-meta">
          <span className="category-tag">{product.category}</span>
          <span className={stock > 0 ? 'stock-copy' : 'stock-copy stock-unavailable'}>
            {stock > 0 ? `${stock} in stock` : 'Currently unavailable'}
          </span>
        </div>
        <h3>{product.name}</h3>
        {product.description && <p className="product-description">{product.description}</p>}
        <div className="variant-table">
          {product.variants.map((variant) => {
            const quantity = quantities[variant.id] ?? 1
            return (
              <div className="variant-row" key={variant.id}>
                <div className="variant-label">
                  <strong>Size {variant.size}</strong>
                  <span>
                    {variant.color || 'Standard'} · {variant.stock_quantity > 0 ? `${variant.stock_quantity} left` : 'Sold out'}
                  </span>
                </div>
                <div className="variant-actions">
                  <span className="variant-price">₹{variant.price.toLocaleString('en-IN')}</span>
                  <label className="sr-only" htmlFor={`quantity-${variant.id}`}>Quantity for {product.name}, size {variant.size}</label>
                  <input
                    id={`quantity-${variant.id}`}
                    className="quantity-input"
                    aria-label={`Quantity for ${product.name}, size ${variant.size}`}
                    type="number"
                    min={1}
                    max={variant.stock_quantity}
                    value={quantity}
                    disabled={variant.stock_quantity === 0}
                    onChange={(event) => {
                      const next = Number(event.target.value)
                      setQuantities((previous) => ({
                        ...previous,
                        [variant.id]: next > 0
                          ? Math.min(next, variant.stock_quantity)
                          : 1,
                      }))
                    }}
                  />
                  <button
                    type="button"
                    className="button button-secondary button-small"
                    disabled={variant.stock_quantity === 0 || addingVariant === variant.id}
                    onClick={() => addVariant(variant)}
                  >
                    {addingVariant === variant.id ? 'Adding…' : variant.stock_quantity === 0 ? 'Sold out' : 'Add'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
        {message && (
          <p className={message === 'Added to cart' ? 'inline-message' : 'inline-message inline-message-error'} role="status">
            {message}
          </p>
        )}
      </div>
    </article>
  )
}
