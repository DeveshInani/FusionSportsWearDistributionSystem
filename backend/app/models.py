from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.db import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    city: Mapped[str] = Column(String(100), nullable=False)
    address: Mapped[str | None] = Column(Text, nullable=True)
    description: Mapped[str] = Column(Text, nullable=True)
    logo_url: Mapped[str] = Column(String(255), nullable=True)

    classes: Mapped[list[SchoolClass]] = relationship(back_populates="school")
    products: Mapped[list[SchoolCatalogItem]] = relationship(back_populates="school")
    users: Mapped[list[User]] = relationship(back_populates="school")


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    school_id: Mapped[int] = Column(ForeignKey("schools.id"), nullable=False)
    grade: Mapped[int] = Column(Integer, nullable=False)
    section: Mapped[str] = Column(String(10), nullable=False)

    school: Mapped[School] = relationship(back_populates="classes")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    email: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    password_hash: Mapped[str] = Column(String(255), nullable=False)
    role: Mapped[str] = Column(String(50), default="student", nullable=False)
    school_id: Mapped[int | None] = Column(ForeignKey("schools.id"), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    school: Mapped[School | None] = relationship(back_populates="users")
    profile: Mapped[StudentProfile | None] = relationship(back_populates="user")
    cart: Mapped[Cart | None] = relationship(back_populates="user")
    orders: Mapped[list[Order]] = relationship(back_populates="user")
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(ForeignKey("users.id"), unique=True, nullable=False)
    school_id: Mapped[int] = Column(ForeignKey("schools.id"), nullable=False)
    grade: Mapped[int] = Column(Integer, nullable=False)
    section: Mapped[str] = Column(String(10), nullable=False)
    class_id: Mapped[int | None] = Column(ForeignKey("school_classes.id"), nullable=True)
    roll_number: Mapped[str | None] = Column(String(30), nullable=True)
    verified_at: Mapped[datetime | None] = Column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")


class StudentRoster(Base):
    __tablename__ = "student_roster"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    school_id: Mapped[int] = Column(ForeignKey("schools.id"), nullable=False)
    class_id: Mapped[int] = Column(ForeignKey("school_classes.id"), nullable=False)
    section: Mapped[str] = Column(String(10), nullable=False)
    roll_number: Mapped[str] = Column(String(30), nullable=False)
    student_name: Mapped[str] = Column(String(255), nullable=False)
    is_claimed: Mapped[bool] = Column(Boolean, default=False, nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String(255), nullable=False)
    category: Mapped[str] = Column(String(120), nullable=False)
    gender: Mapped[str] = Column(String(20), nullable=False, default="unisex")
    description: Mapped[str] = Column(Text, nullable=True)
    image_url: Mapped[str] = Column(String(255), nullable=True)

    variants: Mapped[list[ProductVariant]] = relationship(back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = Column(ForeignKey("products.id"), nullable=False)
    size: Mapped[str] = Column(String(20), nullable=False)
    color: Mapped[str] = Column(String(50), nullable=True)
    stock_quantity: Mapped[int] = Column(Integer, default=0, nullable=False)
    base_price: Mapped[float] = Column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="variants")
    catalog_items: Mapped[list[SchoolCatalogItem]] = relationship(back_populates="variant")


class SchoolCatalogItem(Base):
    __tablename__ = "school_catalog_items"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    school_id: Mapped[int] = Column(ForeignKey("schools.id"), nullable=False)
    variant_id: Mapped[int] = Column(ForeignKey("product_variants.id"), nullable=False)
    selling_price: Mapped[float] = Column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = Column(Integer, default=0, server_default="0", nullable=False)
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)

    school: Mapped[School] = relationship(back_populates="products")
    variant: Mapped[ProductVariant] = relationship(back_populates="catalog_items")


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(ForeignKey("users.id"), unique=True, nullable=False)
    school_id: Mapped[int] = Column(ForeignKey("schools.id"), nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="cart")
    items: Mapped[list[CartItem]] = relationship(back_populates="cart")


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    cart_id: Mapped[int] = Column(ForeignKey("carts.id"), nullable=False)
    catalog_item_id: Mapped[int] = Column(ForeignKey("school_catalog_items.id"), nullable=False)
    quantity: Mapped[int] = Column(Integer, default=1, nullable=False)

    cart: Mapped[Cart] = relationship(back_populates="items")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_created_id", "user_id", "created_at", "id"),
        Index("ix_orders_created_id", "created_at", "id"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    order_number: Mapped[str] = Column(String(40), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = Column(ForeignKey("users.id"), nullable=False)
    school_id: Mapped[int] = Column(ForeignKey("schools.id"), nullable=False)
    total_amount: Mapped[float] = Column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[float] = Column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = Column(Numeric(10, 2), nullable=False, default=0)
    delivery_fee: Mapped[float] = Column(Numeric(10, 2), nullable=False, default=0)
    delivery_address: Mapped[str | None] = Column(Text, nullable=True)
    delivery_area: Mapped[str | None] = Column(String(120), nullable=True)
    delivery_city: Mapped[str | None] = Column(String(100), nullable=True)
    delivery_postal_code: Mapped[str | None] = Column(String(20), nullable=True)
    delivery_latitude: Mapped[float | None] = Column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = Column(Float, nullable=True)
    status: Mapped[str] = Column(String(50), default="pending", nullable=False)
    payment_method: Mapped[str] = Column(String(50), nullable=False)
    payment_status: Mapped[str] = Column(String(50), default="pending", nullable=False)
    fulfillment_method: Mapped[str] = Column(String(50), default="delivery", nullable=False)
    estimated_ready_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")
    payment: Mapped[Payment | None] = relationship(back_populates="order")
    invoice: Mapped[Invoice | None] = relationship(back_populates="order")
    status_history: Mapped[list[OrderStatusHistory]] = relationship(back_populates="order")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    __table_args__ = (
        Index(
            "ix_order_status_history_order_created_id",
            "order_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = Column(ForeignKey("orders.id"), nullable=False)
    status: Mapped[str] = Column(String(50), nullable=False)
    note: Mapped[str] = Column(Text, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    order: Mapped[Order] = relationship(back_populates="status_history")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = Column(ForeignKey("payments.id"), nullable=False)
    event_type: Mapped[str] = Column(String(50), nullable=False)
    message: Mapped[str] = Column(Text, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_variant_id", "variant_id"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = Column(ForeignKey("orders.id"), nullable=False)
    variant_id: Mapped[int] = Column(ForeignKey("product_variants.id"), nullable=False)
    catalog_item_id: Mapped[int | None] = Column(
        ForeignKey("school_catalog_items.id"), nullable=True
    )
    name: Mapped[str] = Column(String(255), nullable=False)
    size: Mapped[str] = Column(String(20), nullable=False)
    color: Mapped[str] = Column(String(50), nullable=True)
    quantity: Mapped[int] = Column(Integer, nullable=False)
    unit_price: Mapped[float] = Column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = Column(ForeignKey("orders.id"), unique=True, nullable=False)
    amount: Mapped[float] = Column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = Column(String(50), nullable=False)
    status: Mapped[str] = Column(String(50), default="paid", nullable=False)
    gateway_reference: Mapped[str | None] = Column(String(255), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    order: Mapped[Order] = relationship(back_populates="payment")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = Column(ForeignKey("orders.id"), unique=True, nullable=False)
    invoice_number: Mapped[str] = Column(String(40), unique=True, nullable=False, index=True)
    pdf_url: Mapped[str | None] = Column(String(255), nullable=True)
    status: Mapped[str] = Column(String(50), default="generated", nullable=False)

    order: Mapped[Order] = relationship(back_populates="invoice")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = Column(String(255), nullable=False)
    body: Mapped[str] = Column(Text, nullable=False)
    is_read: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="notifications")


class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    recipient: Mapped[str] = Column(String(255), nullable=False, index=True)
    subject: Mapped[str] = Column(String(255), nullable=False)
    body: Mapped[str] = Column(Text, nullable=False)
    event_type: Mapped[str] = Column(String(80), nullable=False, index=True)
    status: Mapped[str] = Column(String(30), nullable=False, default="pending")
    error_message: Mapped[str | None] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
