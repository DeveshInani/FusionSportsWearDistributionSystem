export type AuthMode = 'login' | 'register'

export type PageName =
  | 'catalog'
  | 'cart'
  | 'checkout'
  | 'payment'
  | 'confirmation'
  | 'orders'
  | 'order-detail'
  | 'admin'

export type School = {
  id: number
  name: string
  city: string
  address?: string | null
  description?: string
  logo_url?: string
}

export type AdminCatalogItem = {
  catalog_item_id: number
  product_id: number
  name: string
  category: string
  gender: 'boys' | 'girls' | 'unisex'
  description?: string | null
  image_url?: string | null
  size: string
  color?: string | null
  selling_price: number
  stock_quantity: number
  is_active: boolean
}

export type SchoolClass = {
  grade: number
  sections: string[]
}

export type User = {
  id: number
  email: string
  name: string
  role: string
  school_id?: number | null
  grade?: number | null
  section?: string | null
  roll_number?: string | null
  is_verified: boolean
}

export type AuthResponse = {
  access_token: string
  user: User
}

export type ProductVariant = {
  id: number
  catalog_item_id: number
  size: string
  color?: string | null
  stock_quantity: number
  price: number
}

export type Product = {
  id: number
  name: string
  category: string
  gender: 'boys' | 'girls' | 'unisex'
  description?: string | null
  image_url?: string | null
  variants: ProductVariant[]
}

export type CartItem = {
  id: number
  catalog_item_id: number
  product_name: string
  variant_id: number
  size: string
  color?: string | null
  quantity: number
  stock_quantity: number
  unit_price: number
  line_total: number
}

export type Cart = {
  id: number
  school_id: number
  items: CartItem[]
  total: number
}

export type FulfillmentMethod = 'delivery' | 'pickup'
export type PaymentMethod = 'upi' | 'net_banking' | 'cash'

export type QuoteLine = {
  cart_item_id: number
  name: string
  size: string
  quantity: number
  unit_price: number
  line_total: number
}

export type CheckoutQuote = {
  lines: QuoteLine[]
  subtotal: number
  tax: number
  delivery_fee: number
  total: number
  fulfillment_method: FulfillmentMethod
  estimated_ready_at: string
}

export type OrderItem = {
  id: number
  variant_id: number
  name: string
  size: string
  color?: string | null
  quantity: number
  unit_price: number
}

export type OrderHistoryEntry = {
  status: string
  note: string
  created_at: string
}

export type Order = {
  id: number
  order_number: string
  school_id: number
  total_amount: number
  subtotal: number
  tax_amount: number
  delivery_fee: number
  delivery_address?: string | null
  delivery_area?: string | null
  delivery_city?: string | null
  delivery_postal_code?: string | null
  delivery_latitude?: number | null
  delivery_longitude?: number | null
  status: string
  payment_method: string
  payment_status: string
  amount_paid: number
  fulfillment_method: FulfillmentMethod
  estimated_ready_at: string
  created_at: string
  items: OrderItem[]
  invoice_number?: string | null
  status_history: OrderHistoryEntry[]
}

export type NotificationItem = {
  id: number
  title: string
  body: string
  is_read: boolean
}

export type AdminOverview = {
  schools: number
  products: number
  orders: number
  revenue: number
  pending_orders: number
}

export type ProductStat = {
  name: string
  category: string
  gender: string
  units_sold: number
  order_count: number
  revenue: number
}

export type AdminAnalytics = {
  daily_orders: { date: string; orders: number }[]
  top_products: ProductStat[]
  slow_products: ProductStat[]
  category_sales: { category: string; units_sold: number }[]
  gender_sales: { gender: string; units_sold: number }[]
  order_statuses: { status: string; count: number }[]
}

export type SystemHealth = {
  sampled_at: string
  process_rss_mb: number
  process_vms_mb: number
  process_cpu_percent: number
  system_memory_percent: number
  active_requests: number
  peak_concurrent_requests: number
  requests_last_minute: number
  average_latency_ms: number
  p95_latency_ms: number
  process_threads: number
}

export type EmailLog = {
  id: number
  recipient: string
  subject: string
  event_type: string
  status: string
  error_message?: string | null
  created_at: string
}
