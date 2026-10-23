from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(min_length=2, max_length=255)
    school_id: int = Field(gt=0)
    grade: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=10)
    roll_number: str = Field(min_length=1, max_length=30)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserSummary(BaseModel):
    id: int
    email: str
    name: str
    role: str
    school_id: int | None = None
    grade: int | None = None
    section: str | None = None
    roll_number: str | None = None
    is_verified: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class SchoolSummary(BaseModel):
    id: int
    name: str
    city: str
    address: str | None = None
    description: str | None = None
    logo_url: str | None = None


class ClassSummary(BaseModel):
    grade: int
    sections: list[str]


class ProductVariantSummary(BaseModel):
    id: int
    catalog_item_id: int | None = None
    size: str
    color: str | None = None
    stock_quantity: int
    price: float


class ProductDisplay(BaseModel):
    id: int
    name: str
    category: str
    gender: str
    description: str | None = None
    image_url: str | None = None
    variants: list[ProductVariantSummary]


class SchoolClassSelection(BaseModel):
    grade: int = Field(ge=1, le=12)
    sections: list[str] = Field(min_length=1, max_length=12)


class SchoolCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=1000)
    description: str | None = Field(default=None, max_length=2000)
    logo_url: str | None = Field(default=None, max_length=255)
    classes: list[SchoolClassSelection] = Field(min_length=1, max_length=12)


class StudentRosterCreateItem(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    grade: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=10)
    roll_number: str = Field(min_length=1, max_length=30)


class StudentRosterCreateRequest(BaseModel):
    students: list[StudentRosterCreateItem] = Field(min_length=1, max_length=500)


class ProductVariantCreate(BaseModel):
    size: str = Field(min_length=1, max_length=20)
    color: str | None = Field(default=None, max_length=50)
    stock_quantity: int = Field(ge=0, le=100000)
    price: float = Field(gt=0, le=10000000)


class SchoolProductCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    category: str = Field(min_length=2, max_length=80)
    gender: Literal["boys", "girls", "unisex"]
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=255)
    variants: list[ProductVariantCreate] = Field(min_length=1, max_length=50)


class CatalogItemUpdateRequest(BaseModel):
    selling_price: float = Field(gt=0, le=10000000)
    stock_quantity: int = Field(ge=0, le=100000)
    is_active: bool = True


class ProductAdminDisplay(BaseModel):
    catalog_item_id: int
    product_id: int
    name: str
    category: str
    gender: str
    description: str | None = None
    image_url: str | None = None
    size: str
    color: str | None = None
    selling_price: float
    stock_quantity: int
    is_active: bool


class CartItemCreate(BaseModel):
    catalog_item_id: int | None = None
    variant_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartItemRead(BaseModel):
    id: int
    catalog_item_id: int
    product_name: str
    variant_id: int
    size: str
    color: str | None = None
    quantity: int
    stock_quantity: int
    unit_price: float
    line_total: float


class CartRead(BaseModel):
    id: int
    school_id: int
    items: list[CartItemRead]
    total: float


class CheckoutQuoteRequest(BaseModel):
    fulfillment_method: Literal["delivery", "pickup"] = "delivery"


class QuoteLine(BaseModel):
    cart_item_id: int
    name: str
    size: str
    quantity: int
    unit_price: float
    line_total: float


class CheckoutQuote(BaseModel):
    lines: list[QuoteLine]
    subtotal: float
    tax: float
    delivery_fee: float
    total: float
    fulfillment_method: str
    estimated_ready_at: str


class CheckoutRequest(BaseModel):
    payment_method: Literal["upi", "net_banking", "cash"]
    fulfillment_method: Literal["delivery", "pickup"] = "delivery"
    delivery_address: str | None = Field(default=None, min_length=5, max_length=1000)
    delivery_area: str | None = Field(default=None, min_length=2, max_length=120)
    delivery_city: str | None = Field(default=None, min_length=2, max_length=100)
    delivery_postal_code: str | None = Field(default=None, min_length=3, max_length=20)
    delivery_latitude: float | None = Field(default=None, ge=-90, le=90)
    delivery_longitude: float | None = Field(default=None, ge=-180, le=180)


class PaymentSimulationRequest(BaseModel):
    outcome: Literal["success", "failure"]


class OrderStatusRequest(BaseModel):
    status: Literal[
        "processing",
        "preparing",
        "ready_for_pickup",
        "out_for_delivery",
        "delivered",
        "picked_up",
    ]
    note: str | None = Field(default=None, max_length=500)


class OrderItemSelection(BaseModel):
    catalog_item_id: int
    quantity: int = Field(ge=1, le=99)


class OrderItemsUpdateRequest(BaseModel):
    items: list[OrderItemSelection] = Field(min_length=1, max_length=30)


class OrderCancellationRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminProductStat(BaseModel):
    name: str
    category: str
    gender: str
    units_sold: int
    order_count: int
    revenue: float


class AdminAnalytics(BaseModel):
    daily_orders: list[dict[str, int | str]]
    top_products: list[AdminProductStat]
    slow_products: list[AdminProductStat]
    category_sales: list[dict[str, int | str]]
    gender_sales: list[dict[str, int | str]]
    order_statuses: list[dict[str, int | str]]


class SystemHealth(BaseModel):
    sampled_at: str
    process_rss_mb: float
    process_vms_mb: float
    process_cpu_percent: float
    system_memory_percent: float
    active_requests: int
    peak_concurrent_requests: int
    requests_last_minute: int
    average_latency_ms: float
    p95_latency_ms: float
    process_threads: int


class EmailLogRead(BaseModel):
    id: int
    recipient: str
    subject: str
    event_type: str
    status: str
    error_message: str | None = None
    created_at: str


class OrderItemRead(BaseModel):
    id: int
    variant_id: int
    name: str
    size: str
    color: str | None = None
    quantity: int
    unit_price: float


class OrderHistoryEntry(BaseModel):
    status: str
    note: str
    created_at: str


class OrderRead(BaseModel):
    id: int
    order_number: str
    school_id: int
    total_amount: float
    subtotal: float
    tax_amount: float
    delivery_fee: float
    delivery_address: str | None = None
    delivery_area: str | None = None
    delivery_city: str | None = None
    delivery_postal_code: str | None = None
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    status: str
    payment_method: str
    payment_status: str
    amount_paid: float
    fulfillment_method: str
    estimated_ready_at: str
    created_at: str
    items: list[OrderItemRead]
    invoice_number: str | None = None
    status_history: list[OrderHistoryEntry]


class PaymentResult(BaseModel):
    order_id: int
    order_number: str
    order_status: str
    payment_status: str
    message: str


class AdminOverview(BaseModel):
    schools: int
    products: int
    orders: int
    revenue: float
    pending_orders: int


class NotificationRead(BaseModel):
    id: int
    title: str
    body: str
    is_read: bool
