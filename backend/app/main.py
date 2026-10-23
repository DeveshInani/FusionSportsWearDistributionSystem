from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.auth import (
    create_access_token,
    get_current_admin_user,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import SessionLocal, get_db, init_db
from app.models import (
    Cart,
    CartItem,
    EmailLog,
    Invoice,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    PaymentEvent,
    Product,
    ProductVariant,
    School,
    SchoolCatalogItem,
    SchoolClass,
    StudentProfile,
    StudentRoster,
    User,
)
from app.schemas import (
    AdminAnalytics,
    AdminOverview,
    AdminProductStat,
    CartItemCreate,
    CartItemRead,
    CartItemUpdate,
    CartRead,
    CatalogItemUpdateRequest,
    CheckoutQuote,
    CheckoutQuoteRequest,
    CheckoutRequest,
    ClassSummary,
    LoginRequest,
    NotificationRead,
    OrderHistoryEntry,
    OrderCancellationRequest,
    OrderItemsUpdateRequest,
    OrderRead,
    OrderStatusRequest,
    PaymentResult,
    PaymentSimulationRequest,
    ProductDisplay,
    ProductAdminDisplay,
    ProductVariantCreate,
    ProductVariantSummary,
    QuoteLine,
    RegisterRequest,
    SchoolCreateRequest,
    SchoolProductCreateRequest,
    SchoolSummary,
    StudentRosterCreateRequest,
    SystemHealth,
    TokenResponse,
    UserSummary,
    EmailLogRead,
)
from app.seed import seed_demo_data
from app.mailer import send_order_email
from app.telemetry import RequestTelemetryMiddleware, request_telemetry

app = FastAPI(title="School Uniform Store Demo", version="2.0.0")
app.add_middleware(RequestTelemetryMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
MEDIA_DIRECTORY = Path(__file__).resolve().parents[1] / "uploads"
app.mount("/media", StaticFiles(directory=MEDIA_DIRECTORY, check_dir=False), name="media")

ZERO = Decimal("0.00")
TAX_RATE = Decimal("0.05")
DELIVERY_FEE = Decimal("79.00")


@app.on_event("startup")
def startup_event():
    init_db()
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}


def _money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _user_summary(db: Session, user: User) -> UserSummary:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    return UserSummary(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        school_id=user.school_id,
        grade=profile.grade if profile else None,
        section=profile.section if profile else None,
        roll_number=profile.roll_number if profile else None,
        is_verified=profile.verified_at is not None if profile else user.role == "admin",
    )


def _token_response(db: Session, user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token({"sub": user.email}),
        user=_user_summary(db, user),
    )


def _get_verified_profile(db: Session, user: User) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if not profile or not profile.verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified student enrollment is required to shop.",
        )
    return profile


def _get_or_create_cart(
    db: Session,
    user: User,
    school_id: int,
    *,
    lock: bool = False,
) -> Cart:
    query = db.query(Cart).filter(Cart.user_id == user.id)
    if lock:
        query = query.with_for_update()
    cart = query.first()
    if not cart:
        cart = Cart(user_id=user.id, school_id=school_id)
        db.add(cart)
        db.flush()
    if cart.school_id != school_id:
        raise HTTPException(status_code=409, detail="Cart school does not match the verified enrollment.")
    return cart


def _cart_response(db: Session, cart: Cart) -> CartRead:
    items = []
    total = ZERO
    for cart_item in cart.items:
        catalog_item = (
            db.query(SchoolCatalogItem)
            .filter(
                SchoolCatalogItem.id == cart_item.catalog_item_id,
                SchoolCatalogItem.school_id == cart.school_id,
                SchoolCatalogItem.is_active.is_(True),
            )
            .first()
        )
        if not catalog_item:
            continue
        variant = catalog_item.variant
        line_total = _money(catalog_item.selling_price * cart_item.quantity)
        total += line_total
        items.append(
            CartItemRead(
                id=cart_item.id,
                catalog_item_id=catalog_item.id,
                product_name=variant.product.name,
                variant_id=variant.id,
                size=variant.size,
                color=variant.color,
                quantity=cart_item.quantity,
                stock_quantity=catalog_item.stock_quantity,
                unit_price=float(catalog_item.selling_price),
                line_total=float(line_total),
            )
        )
    return CartRead(id=cart.id, school_id=cart.school_id, items=items, total=float(_money(total)))


def _checkout_quote(db: Session, cart: Cart, fulfillment_method: str) -> CheckoutQuote:
    if not cart.items:
        raise HTTPException(status_code=400, detail="Your cart is empty.")

    lines = []
    subtotal = ZERO
    for item in cart.items:
        catalog_item = (
            db.query(SchoolCatalogItem)
            .filter(
                SchoolCatalogItem.id == item.catalog_item_id,
                SchoolCatalogItem.school_id == cart.school_id,
                SchoolCatalogItem.is_active.is_(True),
            )
            .first()
        )
        if not catalog_item or not catalog_item.variant.is_active:
            raise HTTPException(status_code=409, detail="A cart item is no longer available for this school.")
        if item.quantity > catalog_item.stock_quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Only {catalog_item.stock_quantity} of {catalog_item.variant.product.name} ({catalog_item.variant.size}) remain.",
            )

        unit_price = _money(catalog_item.selling_price)
        line_total = _money(unit_price * item.quantity)
        subtotal += line_total
        lines.append(
            QuoteLine(
                cart_item_id=item.id,
                name=catalog_item.variant.product.name,
                size=catalog_item.variant.size,
                quantity=item.quantity,
                unit_price=float(unit_price),
                line_total=float(line_total),
            )
        )

    subtotal = _money(subtotal)
    tax = _money(subtotal * TAX_RATE)
    delivery_fee = DELIVERY_FEE if fulfillment_method == "delivery" else ZERO
    total = _money(subtotal + tax + delivery_fee)
    ready_days = 5 if fulfillment_method == "delivery" else 4
    estimated_ready_at = (datetime.utcnow() + timedelta(days=ready_days)).isoformat()
    return CheckoutQuote(
        lines=lines,
        subtotal=float(subtotal),
        tax=float(tax),
        delivery_fee=float(delivery_fee),
        total=float(total),
        fulfillment_method=fulfillment_method,
        estimated_ready_at=estimated_ready_at,
    )


def _order_response(db: Session, order: Order) -> OrderRead:
    invoice = order.invoice
    payment = order.payment
    history = sorted(order.status_history, key=lambda entry: (entry.created_at, entry.id))
    return OrderRead(
        id=order.id,
        order_number=order.order_number,
        school_id=order.school_id,
        total_amount=float(order.total_amount),
        subtotal=float(order.subtotal),
        tax_amount=float(order.tax_amount),
        delivery_fee=float(order.delivery_fee),
        delivery_address=order.delivery_address,
        delivery_area=order.delivery_area,
        delivery_city=order.delivery_city,
        delivery_postal_code=order.delivery_postal_code,
        delivery_latitude=order.delivery_latitude,
        delivery_longitude=order.delivery_longitude,
        status=order.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        amount_paid=(
            float(payment.amount)
            if payment
            and order.payment_status in {"paid", "adjustment_pending", "adjustment_failed"}
            else 0.0
        ),
        fulfillment_method=order.fulfillment_method,
        estimated_ready_at=(order.estimated_ready_at or order.created_at).isoformat(),
        created_at=order.created_at.isoformat(),
        items=[
            {
                "id": item.id,
                "variant_id": item.variant_id,
                "name": item.name,
                "size": item.size,
                "color": item.color,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
            }
            for item in order.items
        ],
        invoice_number=invoice.invoice_number if invoice else None,
        status_history=[
            OrderHistoryEntry(
                status=entry.status,
                note=entry.note,
                created_at=entry.created_at.isoformat(),
            )
            for entry in history
        ],
    )


def _add_status(db: Session, order: Order, status_name: str, note: str):
    order.status = status_name
    db.add(OrderStatusHistory(order_id=order.id, status=status_name, note=note))


def _notify(db: Session, user_id: int, title: str, body: str):
    db.add(Notification(user_id=user_id, title=title, body=body))


def _reserve_variant_stock(
    db: Session,
    catalog_item_id: int,
    quantity: int,
) -> bool:
    reserved = (
        db.query(SchoolCatalogItem)
        .filter(
            SchoolCatalogItem.id == catalog_item_id,
            SchoolCatalogItem.is_active.is_(True),
            SchoolCatalogItem.stock_quantity >= quantity,
        )
        .update(
            {
                SchoolCatalogItem.stock_quantity:
                    SchoolCatalogItem.stock_quantity - quantity
            },
            synchronize_session=False,
        )
    )
    return bool(reserved)


def _release_order_stock(db: Session, order: Order):
    for item in order.items:
        if item.catalog_item_id is not None:
            db.query(SchoolCatalogItem).filter(
                SchoolCatalogItem.id == item.catalog_item_id
            ).update(
                {
                    SchoolCatalogItem.stock_quantity:
                        SchoolCatalogItem.stock_quantity + item.quantity
                },
                synchronize_session=False,
            )
        else:
            db.query(ProductVariant).filter(ProductVariant.id == item.variant_id).update(
                {
                    ProductVariant.stock_quantity:
                        ProductVariant.stock_quantity + item.quantity
                },
                synchronize_session=False,
            )


@app.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="This email is already registered.")

    school = db.query(School).filter(School.id == payload.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    school_class = (
        db.query(SchoolClass)
        .filter(
            SchoolClass.school_id == school.id,
            SchoolClass.grade == payload.grade,
            SchoolClass.section == payload.section.strip().upper(),
        )
        .first()
    )
    if not school_class:
        raise HTTPException(status_code=404, detail="The selected class and section are not available.")

    roster_entry = (
        db.query(StudentRoster)
        .filter(
            StudentRoster.school_id == school.id,
            StudentRoster.class_id == school_class.id,
            StudentRoster.section == school_class.section,
            func.lower(StudentRoster.roll_number) == payload.roll_number.strip().lower(),
        )
        .with_for_update()
        .first()
    )
    if not roster_entry or roster_entry.student_name.casefold() != payload.name.strip().casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="We couldn't verify these details against the school's student roster.",
        )
    if roster_entry.is_claimed:
        raise HTTPException(status_code=409, detail="This student roll number has already been registered.")

    user = User(
        email=payload.email.lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role="student",
        school_id=school.id,
    )
    db.add(user)
    db.flush()
    db.add(
        StudentProfile(
            user_id=user.id,
            school_id=school.id,
            grade=school_class.grade,
            section=school_class.section,
            class_id=school_class.id,
            roll_number=roster_entry.roll_number,
            verified_at=datetime.utcnow(),
        )
    )
    roster_entry.is_claimed = True
    db.add(Cart(user_id=user.id, school_id=school.id))
    db.commit()
    db.refresh(user)
    return _token_response(db, user)


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return _token_response(db, user)


@app.get("/me", response_model=UserSummary)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _user_summary(db, current_user)


@app.get("/schools", response_model=list[SchoolSummary])
def list_schools(db: Session = Depends(get_db)):
    return [
        SchoolSummary(
            id=school.id,
            name=school.name,
            city=school.city,
            address=school.address,
            description=school.description,
            logo_url=school.logo_url,
        )
        for school in db.query(School).order_by(School.name).all()
    ]


def _validate_image_url(image_url: str | None) -> str | None:
    if image_url is None or not image_url.strip():
        return None
    candidate = image_url.strip()
    parsed = urlsplit(candidate)
    if candidate.startswith(("/media/", "/api/media/")) or (
        parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password
    ):
        return candidate
    raise HTTPException(
        status_code=422,
        detail="Images must use an uploaded /media URL or a secure HTTPS URL.",
    )


@app.post("/admin/schools", response_model=SchoolSummary, status_code=status.HTTP_201_CREATED)
def create_school(
    payload: SchoolCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if db.query(School.id).filter(func.lower(School.name) == name.lower()).first():
        raise HTTPException(status_code=409, detail="A school with this name already exists.")

    seen_classes: set[tuple[int, str]] = set()
    classes: list[SchoolClass] = []
    for entry in payload.classes:
        for raw_section in entry.sections:
            section = raw_section.strip().upper()
            key = (entry.grade, section)
            if not section or key in seen_classes:
                raise HTTPException(
                    status_code=422,
                    detail="Class sections must be unique and cannot be blank.",
                )
            seen_classes.add(key)
            classes.append(
                SchoolClass(grade=entry.grade, section=section)
            )

    school = School(
        name=name,
        city=payload.city.strip(),
        address=payload.address.strip(),
        description=payload.description.strip() if payload.description else None,
        logo_url=_validate_image_url(payload.logo_url),
    )
    db.add(school)
    db.flush()
    for school_class in classes:
        school_class.school_id = school.id
        db.add(school_class)
    db.commit()
    db.refresh(school)
    return school


@app.post(
    "/admin/schools/{school_id}/roster",
    status_code=status.HTTP_201_CREATED,
)
def add_school_roster(
    school_id: int,
    payload: StudentRosterCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    seen_roll_numbers: set[str] = set()
    roster_rows: list[StudentRoster] = []
    for student in payload.students:
        section = student.section.strip().upper()
        roll_number = student.roll_number.strip()
        roll_key = roll_number.casefold()
        if roll_key in seen_roll_numbers or db.query(StudentRoster.id).filter(
            StudentRoster.school_id == school_id,
            func.lower(StudentRoster.roll_number) == roll_key,
        ).first():
            raise HTTPException(
                status_code=409,
                detail=f"Roll number '{roll_number}' is already on this school's roster.",
            )
        school_class = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.school_id == school_id,
                SchoolClass.grade == student.grade,
                SchoolClass.section == section,
            )
            .first()
        )
        if not school_class:
            raise HTTPException(
                status_code=422,
                detail=f"Class {student.grade}{section} is not configured for this school.",
            )
        seen_roll_numbers.add(roll_key)
        roster_rows.append(
            StudentRoster(
                school_id=school_id,
                class_id=school_class.id,
                section=section,
                roll_number=roll_number,
                student_name=student.name.strip(),
                is_claimed=False,
            )
        )
    db.add_all(roster_rows)
    db.commit()
    return {"created": len(roster_rows)}


@app.post("/admin/uploads/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin_user),
):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPG, PNG, or WebP image.",
        )
    contents = await file.read(5 * 1024 * 1024 + 1)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image files must be 5 MB or smaller.")
    if not contents:
        raise HTTPException(status_code=400, detail="The selected image is empty.")

    try:
        with Image.open(BytesIO(contents)) as uploaded:
            if uploaded.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=415, detail="Unsupported image format.")
            uploaded.verify()
        with Image.open(BytesIO(contents)) as uploaded:
            if uploaded.width > 8000 or uploaded.height > 8000:
                raise HTTPException(
                    status_code=422,
                    detail="Image dimensions must be 8000 by 8000 pixels or smaller.",
                )
            uploaded.thumbnail((1800, 1800))
            image = uploaded.convert("RGB")
            image_name = f"{uuid4().hex}.jpg"
            MEDIA_DIRECTORY.mkdir(parents=True, exist_ok=True)
            image.save(MEDIA_DIRECTORY / image_name, format="JPEG", quality=86, optimize=True)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid image.") from exc
    finally:
        await file.close()

    return {"image_url": f"/api/media/{image_name}"}


@app.get(
    "/admin/schools/{school_id}/products",
    response_model=list[ProductAdminDisplay],
)
def admin_school_products(
    school_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    if not db.query(School.id).filter(School.id == school_id).first():
        raise HTTPException(status_code=404, detail="School not found.")
    items = (
        db.query(SchoolCatalogItem)
        .join(ProductVariant, ProductVariant.id == SchoolCatalogItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .filter(SchoolCatalogItem.school_id == school_id)
        .order_by(Product.name, ProductVariant.size, SchoolCatalogItem.id)
        .all()
    )
    return [
        ProductAdminDisplay(
            catalog_item_id=item.id,
            product_id=item.variant.product.id,
            name=item.variant.product.name,
            category=item.variant.product.category,
            gender=item.variant.product.gender,
            description=item.variant.product.description,
            image_url=item.variant.product.image_url,
            size=item.variant.size,
            color=item.variant.color,
            selling_price=float(item.selling_price),
            stock_quantity=item.stock_quantity,
            is_active=item.is_active and item.variant.is_active,
        )
        for item in items
    ]


@app.post(
    "/admin/schools/{school_id}/products",
    response_model=list[ProductAdminDisplay],
    status_code=status.HTTP_201_CREATED,
)
def create_school_product(
    school_id: int,
    payload: SchoolProductCreateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    seen_variants: set[tuple[str, str]] = set()
    for variant in payload.variants:
        key = (variant.size.strip().casefold(), (variant.color or "").strip().casefold())
        if key in seen_variants:
            raise HTTPException(
                status_code=422,
                detail="Product size and color combinations must be unique.",
            )
        seen_variants.add(key)
    product = Product(
        name=payload.name.strip(),
        category=payload.category.strip(),
        gender=payload.gender,
        description=payload.description.strip() if payload.description else None,
        image_url=_validate_image_url(payload.image_url),
    )
    db.add(product)
    db.flush()
    created_items: list[SchoolCatalogItem] = []
    for variant_payload in payload.variants:
        variant = ProductVariant(
            product_id=product.id,
            size=variant_payload.size.strip(),
            color=variant_payload.color.strip() if variant_payload.color else None,
            stock_quantity=variant_payload.stock_quantity,
            base_price=variant_payload.price,
            is_active=True,
        )
        db.add(variant)
        db.flush()
        catalog_item = SchoolCatalogItem(
            school_id=school_id,
            variant_id=variant.id,
            selling_price=variant_payload.price,
            stock_quantity=variant_payload.stock_quantity,
            is_active=True,
        )
        db.add(catalog_item)
        created_items.append(catalog_item)
    db.commit()
    return [
        ProductAdminDisplay(
            catalog_item_id=item.id,
            product_id=product.id,
            name=product.name,
            category=product.category,
            gender=product.gender,
            description=product.description,
            image_url=product.image_url,
            size=item.variant.size,
            color=item.variant.color,
            selling_price=float(item.selling_price),
            stock_quantity=item.stock_quantity,
            is_active=item.is_active,
        )
        for item in created_items
    ]


@app.patch(
    "/admin/catalog-items/{catalog_item_id}",
    response_model=ProductAdminDisplay,
)
def update_catalog_item(
    catalog_item_id: int,
    payload: CatalogItemUpdateRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(SchoolCatalogItem)
        .filter(SchoolCatalogItem.id == catalog_item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Catalog item not found.")
    item.selling_price = _money(payload.selling_price)
    item.stock_quantity = payload.stock_quantity
    item.is_active = payload.is_active
    db.commit()
    return ProductAdminDisplay(
        catalog_item_id=item.id,
        product_id=item.variant.product.id,
        name=item.variant.product.name,
        category=item.variant.product.category,
        gender=item.variant.product.gender,
        description=item.variant.product.description,
        image_url=item.variant.product.image_url,
        size=item.variant.size,
        color=item.variant.color,
        selling_price=float(item.selling_price),
        stock_quantity=item.stock_quantity,
        is_active=item.is_active and item.variant.is_active,
    )


@app.get("/schools/{school_id}/classes", response_model=list[ClassSummary])
def list_school_classes(school_id: int, db: Session = Depends(get_db)):
    if not db.query(School.id).filter(School.id == school_id).first():
        raise HTTPException(status_code=404, detail="School not found.")
    classes = (
        db.query(SchoolClass)
        .filter(SchoolClass.school_id == school_id)
        .order_by(SchoolClass.grade, SchoolClass.section)
        .all()
    )
    grouped: dict[int, list[str]] = {}
    for school_class in classes:
        grouped.setdefault(school_class.grade, []).append(school_class.section)
    return [ClassSummary(grade=grade, sections=sections) for grade, sections in grouped.items()]


@app.get("/products", response_model=list[ProductDisplay])
def list_products(
    school_id: int | None = Query(default=None),
    gender: Literal["boys", "girls", "unisex"] | None = Query(default=None),
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_verified_profile(db, current_user)
    target_school_id = profile.school_id
    if school_id is not None and school_id != target_school_id:
        raise HTTPException(status_code=403, detail="Catalog access is limited to your verified school.")
    catalog_items = (
        db.query(SchoolCatalogItem)
        .join(ProductVariant, ProductVariant.id == SchoolCatalogItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .filter(
            SchoolCatalogItem.school_id == target_school_id,
            SchoolCatalogItem.is_active.is_(True),
        )
        .order_by(SchoolCatalogItem.id)
    )
    if gender:
        catalog_items = catalog_items.filter(Product.gender == gender)
    if category:
        catalog_items = catalog_items.filter(Product.category == category)
    catalog_items = catalog_items.all()
    grouped: dict[int, ProductDisplay] = {}
    for item in catalog_items:
        variant = item.variant
        product = variant.product
        if not variant.is_active:
            continue
        if product.id not in grouped:
            grouped[product.id] = ProductDisplay(
                id=product.id,
                name=product.name,
                category=product.category,
                gender=product.gender,
                description=product.description,
                image_url=product.image_url,
                variants=[],
            )
        grouped[product.id].variants.append(
            ProductVariantSummary(
                id=variant.id,
                catalog_item_id=item.id,
                size=variant.size,
                color=variant.color,
                stock_quantity=item.stock_quantity,
                price=float(item.selling_price),
            )
        )
    return list(grouped.values())


@app.get("/cart", response_model=CartRead)
def get_cart(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _get_verified_profile(db, current_user)
    cart = _get_or_create_cart(db, current_user, profile.school_id)
    db.commit()
    return _cart_response(db, cart)


@app.post("/cart/items", response_model=CartRead)
def add_cart_item(
    payload: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_verified_profile(db, current_user)
    if payload.catalog_item_id is None and payload.variant_id is None:
        raise HTTPException(status_code=422, detail="A catalog item is required.")
    query = db.query(SchoolCatalogItem).filter(
        SchoolCatalogItem.school_id == profile.school_id,
        SchoolCatalogItem.is_active.is_(True),
    )
    if payload.catalog_item_id is not None:
        query = query.filter(SchoolCatalogItem.id == payload.catalog_item_id)
    else:
        query = query.filter(SchoolCatalogItem.variant_id == payload.variant_id)
    catalog_item = query.first()
    if not catalog_item or not catalog_item.variant.is_active:
        raise HTTPException(status_code=404, detail="This item is not available in your school catalog.")

    cart = _get_or_create_cart(db, current_user, profile.school_id, lock=True)
    existing = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.catalog_item_id == catalog_item.id,
        )
        .first()
    )
    next_quantity = (existing.quantity if existing else 0) + payload.quantity
    if next_quantity > catalog_item.stock_quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Only {catalog_item.stock_quantity} of this size are currently in stock.",
        )
    if next_quantity > 99:
        raise HTTPException(status_code=422, detail="A maximum of 99 of each size can be added.")
    if existing:
        existing.quantity = next_quantity
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                catalog_item_id=catalog_item.id,
                quantity=payload.quantity,
            )
        )
    db.commit()
    return _cart_response(db, cart)


@app.patch("/cart/items/{cart_item_id}", response_model=CartRead)
def update_cart_item(
    cart_item_id: int,
    payload: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_verified_profile(db, current_user)
    cart = _get_or_create_cart(db, current_user, profile.school_id, lock=True)
    item = (
        db.query(CartItem)
        .filter(CartItem.id == cart_item_id, CartItem.cart_id == cart.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    catalog_item = db.query(SchoolCatalogItem).filter(SchoolCatalogItem.id == item.catalog_item_id).first()
    if not catalog_item or payload.quantity > catalog_item.stock_quantity:
        raise HTTPException(status_code=409, detail="Requested quantity exceeds current stock.")
    item.quantity = payload.quantity
    db.commit()
    return _cart_response(db, cart)


@app.delete("/cart/items/{cart_item_id}", response_model=CartRead)
def remove_cart_item(
    cart_item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_verified_profile(db, current_user)
    cart = _get_or_create_cart(db, current_user, profile.school_id, lock=True)
    item = (
        db.query(CartItem)
        .filter(CartItem.id == cart_item_id, CartItem.cart_id == cart.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    db.delete(item)
    db.commit()
    return _cart_response(db, cart)


@app.post("/checkout/quote", response_model=CheckoutQuote)
def get_checkout_quote(
    payload: CheckoutQuoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_verified_profile(db, current_user)
    cart = _get_or_create_cart(db, current_user, profile.school_id)
    return _checkout_quote(db, cart, payload.fulfillment_method)


@app.post("/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_verified_profile(db, current_user)
    if payload.fulfillment_method == "delivery":
        address_parts = {
            "delivery_address": payload.delivery_address,
            "delivery_area": payload.delivery_area,
            "delivery_city": payload.delivery_city,
            "delivery_postal_code": payload.delivery_postal_code,
        }
        missing = [field for field, value in address_parts.items() if not value or not value.strip()]
        if missing:
            raise HTTPException(
                status_code=422,
                detail="Enter the street address, area, city, and postal code for delivery.",
            )
        if (payload.delivery_latitude is None) != (payload.delivery_longitude is None):
            raise HTTPException(
                status_code=422,
                detail="Both GPS coordinates are required when sharing your location.",
            )
    elif payload.delivery_latitude is not None or payload.delivery_longitude is not None:
        raise HTTPException(
            status_code=422,
            detail="A GPS location is only accepted for home delivery.",
        )
    cart = _get_or_create_cart(db, current_user, profile.school_id, lock=True)
    quote = _checkout_quote(db, cart, payload.fulfillment_method)
    cart_items = list(cart.items)

    order_number = f"PUW-{datetime.utcnow():%y%m%d}-{uuid4().hex[:6].upper()}"
    payment_method_names = {
        "upi": "UPI",
        "net_banking": "Net banking",
        "cash": "Cash at store",
    }
    order_status = "awaiting_payment"
    order = Order(
        order_number=order_number,
        user_id=current_user.id,
        school_id=profile.school_id,
        subtotal=_money(quote.subtotal),
        tax_amount=_money(quote.tax),
        delivery_fee=_money(quote.delivery_fee),
        total_amount=_money(quote.total),
        status=order_status,
        payment_method=payment_method_names[payload.payment_method],
        payment_status="pending",
        fulfillment_method=payload.fulfillment_method,
        estimated_ready_at=datetime.fromisoformat(quote.estimated_ready_at),
        delivery_address=(
            payload.delivery_address.strip()
            if payload.fulfillment_method == "delivery" and payload.delivery_address
            else None
        ),
        delivery_area=(
            payload.delivery_area.strip()
            if payload.fulfillment_method == "delivery" and payload.delivery_area
            else None
        ),
        delivery_city=(
            payload.delivery_city.strip()
            if payload.fulfillment_method == "delivery" and payload.delivery_city
            else None
        ),
        delivery_postal_code=(
            payload.delivery_postal_code.strip()
            if payload.fulfillment_method == "delivery" and payload.delivery_postal_code
            else None
        ),
        delivery_latitude=(
            payload.delivery_latitude if payload.fulfillment_method == "delivery" else None
        ),
        delivery_longitude=(
            payload.delivery_longitude if payload.fulfillment_method == "delivery" else None
        ),
    )
    db.add(order)
    db.flush()

    for cart_item in cart_items:
        catalog_item = (
            db.query(SchoolCatalogItem)
            .filter(
                SchoolCatalogItem.id == cart_item.catalog_item_id,
                SchoolCatalogItem.school_id == profile.school_id,
                SchoolCatalogItem.is_active.is_(True),
            )
            .first()
        )
        if not catalog_item or not catalog_item.variant.is_active:
            db.rollback()
            raise HTTPException(status_code=409, detail="A cart item is no longer available.")
        if not _reserve_variant_stock(db, catalog_item.id, cart_item.quantity):
            db.rollback()
            raise HTTPException(status_code=409, detail="Stock changed while placing your order. Review your cart.")
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=catalog_item.variant_id,
                catalog_item_id=catalog_item.id,
                name=catalog_item.variant.product.name,
                size=catalog_item.variant.size,
                color=catalog_item.variant.color,
                quantity=cart_item.quantity,
                unit_price=_money(catalog_item.selling_price),
            )
        )

    payment = Payment(
        order_id=order.id,
        amount=_money(quote.total),
        method=payment_method_names[payload.payment_method],
        status="pending",
        gateway_reference=f"demo-{uuid4().hex[:12]}",
    )
    db.add(payment)
    db.flush()
    db.add(
        Invoice(
            order_id=order.id,
            invoice_number=f"INV-{order.id:06d}",
            pdf_url=f"/orders/{order.id}/invoice",
            status="generated",
        )
    )
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            status=order_status,
            note=(
                "Order placed. Cash payment is due at the store."
                if payload.payment_method == "cash"
                else "Order created. Complete the simulated payment to start fulfillment."
            ),
        )
    )
    db.add(
        PaymentEvent(
            payment_id=payment.id,
            event_type="created",
            message=f"Demo {payment_method_names[payload.payment_method]} payment created.",
        )
    )
    _notify(
        db,
        current_user.id,
        "Order placed",
        f"Order {order_number} was placed. "
        + ("Pay at the store when you collect it." if payload.payment_method == "cash" else "Complete payment to begin fulfillment."),
    )
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    db.refresh(order)
    send_order_email(
        order.id,
        "order_placed",
        f"Order received: {order.order_number}",
        f"Order {order.order_number} was received. "
        f"Current payment status: {order.payment_status}. Total: INR {order.total_amount:.2f}.",
    )
    return _order_response(db, order)


@app.post("/orders/{order_id}/payment/simulate", response_model=PaymentResult)
def simulate_payment(
    order_id: int,
    payload: PaymentSimulationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.payment_method == "Cash at store":
        raise HTTPException(status_code=400, detail="Cash payment is confirmed by a store cashier.")
    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if payment.status == "paid":
        return PaymentResult(
            order_id=order.id,
            order_number=order.order_number,
            order_status=order.status,
            payment_status=payment.status,
            message="Payment was already successful.",
        )
    if order.status != "awaiting_payment" or payment.status not in {"pending", "failed"}:
        raise HTTPException(status_code=409, detail="This order is not waiting for a payment attempt.")

    retrying_failed_payment = payment.status == "failed"
    if retrying_failed_payment:
        for item in order.items:
            if item.catalog_item_id is None or not _reserve_variant_stock(
                db, item.catalog_item_id, item.quantity
            ):
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock to retry payment for {item.name} ({item.size}). Cancel the order or contact the store.",
                )
        payment.status = "pending"

    if payload.outcome == "failure":
        payment.status = "failed"
        order.payment_status = "failed"
        _release_order_stock(db, order)
        _add_status(db, order, "awaiting_payment", "The simulated payment was declined. No payment was taken and reserved stock was released; you can retry or cancel.")
        message = "Payment failed. No money was taken and reserved stock has been released."
        _notify(db, current_user.id, "Payment not completed", f"Payment for {order.order_number} failed.")
        event_type = "failed"
    else:
        payment.status = "paid"
        order.payment_status = "paid"
        _add_status(db, order, "processing", "Payment succeeded. The order was received and is ready for the store to prepare.")
        message = "Payment successful. Your order is now being prepared."
        _notify(db, current_user.id, "Payment confirmed", f"Payment for {order.order_number} was successful.")
        event_type = "succeeded"

    db.add(PaymentEvent(payment_id=payment.id, event_type=event_type, message=message))
    db.commit()
    send_order_email(
        order.id,
        "payment_confirmed" if payload.outcome == "success" else "payment_failed",
        f"Payment {payment.status}: {order.order_number}",
        f"{message} Order total: INR {order.total_amount:.2f}.",
    )
    return PaymentResult(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        payment_status=payment.status,
        message=message,
    )


@app.get("/orders", response_model=list[OrderRead])
def list_orders(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.payment),
            selectinload(Order.invoice),
            selectinload(Order.status_history),
        )
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_order_response(db, order) for order in orders]


@app.get("/orders/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _order_response(db, order)


@app.put("/orders/{order_id}/items", response_model=OrderRead)
def modify_order_items(
    order_id: int,
    payload: OrderItemsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .with_for_update()
        .first()
    )
    can_modify_unpaid_order = (
        order.status == "awaiting_payment"
        and order.payment_status == "pending"
    )
    can_modify_paid_order = (
        order.status == "processing"
        and order.payment_status == "paid"
    )
    if not (can_modify_unpaid_order or can_modify_paid_order):
        raise HTTPException(
            status_code=409,
            detail="Items can only be changed while payment is pending or after payment, before store preparation. Resolve any payment adjustment first.",
        )

    requested: dict[int, int] = {}
    for entry in payload.items:
        if entry.catalog_item_id in requested:
            raise HTTPException(status_code=422, detail="Each catalog item can only appear once in an order update.")
        requested[entry.catalog_item_id] = entry.quantity

    catalog_items = (
        db.query(SchoolCatalogItem)
        .filter(
            SchoolCatalogItem.id.in_(requested),
            SchoolCatalogItem.school_id == order.school_id,
            SchoolCatalogItem.is_active.is_(True),
        )
        .all()
    )
    by_catalog_id = {entry.id: entry for entry in catalog_items}
    if len(by_catalog_id) != len(requested):
        raise HTTPException(status_code=403, detail="An item is not in this student's school catalog.")

    existing_by_variant = {item.variant_id: item for item in order.items}
    requested_by_variant: dict[int, tuple[SchoolCatalogItem, int]] = {}
    for catalog_id, quantity in requested.items():
        catalog_item = by_catalog_id[catalog_id]
        variant = catalog_item.variant
        if not variant.is_active:
            raise HTTPException(status_code=409, detail=f"{variant.product.name} is no longer available.")
        if variant.id in requested_by_variant:
            raise HTTPException(status_code=422, detail="A product size can only appear once in an order update.")
        requested_by_variant[variant.id] = (catalog_item, quantity)

    old_total = _money(order.total_amount)
    old_items = {
        item.variant_id: (item.quantity, _money(item.unit_price))
        for item in order.items
    }
    no_changes = (
        set(existing_by_variant) == set(requested_by_variant)
        and all(
            old_items[variant_id]
            == (quantity, _money(catalog_item.selling_price))
            for variant_id, (catalog_item, quantity) in requested_by_variant.items()
        )
    )
    if no_changes:
        return _order_response(db, order)

    for variant_id, (catalog_item, quantity) in requested_by_variant.items():
        existing = existing_by_variant.get(variant_id)
        previous_quantity = existing.quantity if existing else 0
        increase = quantity - previous_quantity
        if increase > 0:
            if not _reserve_variant_stock(db, catalog_item.id, increase):
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient current stock for {catalog_item.variant.product.name} ({catalog_item.variant.size}). No order changes were saved.",
                )
        elif increase < 0:
            db.query(SchoolCatalogItem).filter(
                SchoolCatalogItem.id == (existing.catalog_item_id if existing else catalog_item.id)
            ).update(
                {
                    SchoolCatalogItem.stock_quantity:
                        SchoolCatalogItem.stock_quantity - increase
                },
                synchronize_session=False,
            )

        if existing:
            existing.quantity = quantity
            existing.catalog_item_id = catalog_item.id
            existing.unit_price = _money(catalog_item.selling_price)
        else:
            db.add(
                OrderItem(
                    order_id=order.id,
                    variant_id=variant_id,
                    catalog_item_id=catalog_item.id,
                    name=catalog_item.variant.product.name,
                    size=catalog_item.variant.size,
                    color=catalog_item.variant.color,
                    quantity=quantity,
                    unit_price=_money(catalog_item.selling_price),
                )
            )

    for variant_id, existing in existing_by_variant.items():
        if variant_id not in requested_by_variant:
            if existing.catalog_item_id is not None:
                db.query(SchoolCatalogItem).filter(
                    SchoolCatalogItem.id == existing.catalog_item_id
                ).update(
                    {
                        SchoolCatalogItem.stock_quantity:
                            SchoolCatalogItem.stock_quantity + existing.quantity
                    },
                    synchronize_session=False,
                )
            else:
                db.query(ProductVariant).filter(ProductVariant.id == variant_id).update(
                    {
                        ProductVariant.stock_quantity:
                            ProductVariant.stock_quantity + existing.quantity
                    },
                    synchronize_session=False,
                )
            db.delete(existing)

    subtotal = _money(
        sum(
            (_money(catalog_item.selling_price) * quantity for catalog_item, quantity in requested_by_variant.values()),
            ZERO,
        )
    )
    tax = _money(subtotal * TAX_RATE)
    delivery_fee = DELIVERY_FEE if order.fulfillment_method == "delivery" else ZERO
    order.subtotal = subtotal
    order.tax_amount = tax
    order.delivery_fee = delivery_fee
    order.total_amount = _money(subtotal + tax + delivery_fee)
    new_total = _money(order.total_amount)
    if not payment:
        db.rollback()
        raise HTTPException(status_code=409, detail="Payment record is missing; no order changes were saved.")
    if can_modify_unpaid_order:
        payment.amount = new_total
        note = (
            f"Student updated order items before payment. "
            f"New subtotal INR {subtotal:.2f}, tax INR {tax:.2f}, "
            f"delivery INR {delivery_fee:.2f}, total INR {new_total:.2f}."
        )
    else:
        difference = _money(new_total - _money(payment.amount))
        if difference:
            order.payment_status = "adjustment_pending"
            payment.status = "adjustment_pending"
            adjustment_action = "additional payment" if difference > ZERO else "refund"
            db.add(
                PaymentEvent(
                    payment_id=payment.id,
                    event_type="adjustment_required",
                    message=(
                        f"Order total changed from INR {old_total:.2f} to INR {new_total:.2f}. "
                        f"An adjustment {adjustment_action} of INR {abs(difference):.2f} is required."
                    ),
                )
            )
            note = (
                f"Student updated order items. New subtotal INR {subtotal:.2f}, "
                f"tax INR {tax:.2f}, delivery INR {delivery_fee:.2f}, "
                f"total INR {new_total:.2f}. Adjustment {adjustment_action}: "
                f"INR {abs(difference):.2f}."
            )
        else:
            note = (
                f"Student updated order items. New subtotal INR {subtotal:.2f}, "
                f"tax INR {tax:.2f}, delivery INR {delivery_fee:.2f}, "
                f"total INR {new_total:.2f}; no payment adjustment is due."
            )
    _add_status(db, order, order.status, note)
    _notify(db, current_user.id, "Order updated", f"Items on {order.order_number} were updated.")
    db.commit()
    send_order_email(
        order.id,
        "order_modified",
        f"Order updated: {order.order_number}",
        f"{note} Payment status: {order.payment_status}.",
    )
    return _order_response(db, order)


@app.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_student_order(
    order_id: int,
    payload: OrderCancellationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status not in {"awaiting_payment", "processing"}:
        raise HTTPException(status_code=409, detail="This order can no longer be cancelled online.")

    reason = payload.reason.strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Please provide a cancellation reason of at least 3 characters.")
    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .with_for_update()
        .first()
    )
    if order.payment_status not in {"failed", "refunded", "cancelled"}:
        _release_order_stock(db, order)
    refund_amount = _money(payment.amount) if payment else ZERO
    if payment:
        if order.payment_status in {"paid", "adjustment_pending", "adjustment_failed"}:
            payment.status = "refunded"
            order.payment_status = "refunded"
            db.add(
                PaymentEvent(
                    payment_id=payment.id,
                    event_type="refund_simulated",
                    message=f"Cancellation recorded. Simulated refund: INR {refund_amount:.2f}; no real money was moved.",
                )
            )
        else:
            payment.status = "cancelled"
            order.payment_status = "cancelled"
    note = f"Student cancelled order. Reason: {reason}"
    _add_status(db, order, "cancelled", note)
    _notify(db, current_user.id, "Order cancelled", f"{order.order_number} was cancelled. {note}")
    db.commit()
    send_order_email(
        order.id,
        "order_cancelled",
        f"Order cancelled: {order.order_number}",
        f"{note} Payment status: {order.payment_status}. "
        + (f"Simulated refund: INR {refund_amount:.2f}." if order.payment_status == "refunded" else "No refund is due."),
    )
    return _order_response(db, order)


@app.post("/orders/{order_id}/payment/adjustment/simulate", response_model=PaymentResult)
def simulate_order_adjustment(
    order_id: int,
    payload: PaymentSimulationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != "processing" or order.payment_status not in {"adjustment_pending", "adjustment_failed"}:
        raise HTTPException(status_code=409, detail="There is no payment adjustment that can be completed or retried.")
    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    difference = _money(_money(order.total_amount) - _money(payment.amount))
    if difference == ZERO:
        payment.status = "paid"
        order.payment_status = "paid"
        message = "The order total now matches the amount already paid. No payment adjustment was needed."
        event_type = "adjustment_not_required"
    elif payload.outcome == "success":
        payment.amount = _money(order.total_amount)
        payment.status = "paid"
        order.payment_status = "paid"
        action = "additional payment" if difference > ZERO else "refund"
        message = f"The simulated {action} of INR {abs(difference):.2f} succeeded."
        event_type = "adjustment_charge_succeeded" if difference > ZERO else "adjustment_refund_succeeded"
    else:
        payment.status = "adjustment_failed"
        order.payment_status = "adjustment_failed"
        action = "additional payment" if difference > ZERO else "refund"
        message = f"The simulated {action} of INR {abs(difference):.2f} failed. Retry it or cancel the order."
        event_type = "adjustment_charge_failed" if difference > ZERO else "adjustment_refund_failed"
    db.add(PaymentEvent(payment_id=payment.id, event_type=event_type, message=message))
    db.add(OrderStatusHistory(order_id=order.id, status=order.status, note=message))
    _notify(db, current_user.id, "Order payment adjustment", f"{order.order_number}: {message}")
    db.commit()
    send_order_email(
        order.id,
        event_type,
        f"Order payment update: {order.order_number}",
        message,
    )
    return PaymentResult(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.status,
        payment_status=order.payment_status,
        message=message,
    )


@app.get("/orders/{order_id}/invoice")
def download_invoice(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return _render_invoice(order, invoice)


@app.get("/admin/orders/{order_id}/invoice")
def admin_download_invoice(
    order_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    invoice = db.query(Invoice).filter(Invoice.order_id == order.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return _render_invoice(order, invoice)


def _render_invoice(order: Order, invoice: Invoice):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Invoice {invoice.invoice_number}")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(52, 790, "Prodigy Uniform Wear")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(52, 760, f"Demo invoice: {invoice.invoice_number}")
    pdf.drawString(52, 742, f"Order: {order.order_number}")
    pdf.drawString(52, 724, f"Date: {order.created_at:%d %b %Y}")
    pdf.drawString(52, 706, f"Payment: {order.payment_method} ({order.payment_status})")
    y = 660
    for item in order.items:
        pdf.drawString(52, y, f"{item.name} / {item.size}  x{item.quantity}")
        pdf.drawRightString(540, y, f"INR {float(item.unit_price * item.quantity):.2f}")
        y -= 22
        if y < 120:
            pdf.showPage()
            y = 790
    y -= 20
    for label, amount in (
        ("Subtotal", order.subtotal),
        ("Tax", order.tax_amount),
        ("Delivery", order.delivery_fee),
        ("Total", order.total_amount),
    ):
        pdf.drawString(350, y, label)
        pdf.drawRightString(540, y, f"INR {float(amount):.2f}")
        y -= 20
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(52, 60, "This is a demonstration invoice. No real payment was processed.")
    pdf.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@app.get("/notifications", response_model=list[NotificationRead])
def get_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [
        NotificationRead(
            id=item.id,
            title=item.title,
            body=item.body,
            is_read=item.is_read,
        )
        for item in items
    ]


@app.get("/admin/overview", response_model=AdminOverview)
def admin_overview(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return AdminOverview(
        schools=db.query(School).count(),
        products=db.query(Product).count(),
        orders=db.query(Order).count(),
        revenue=float(
            db.query(func.coalesce(func.sum(Order.total_amount), 0))
            .filter(Order.payment_status == "paid")
            .scalar()
            or 0
        ),
        pending_orders=db.query(Order)
        .filter(Order.payment_status.in_(["pending", "adjustment_pending", "adjustment_failed"]))
        .count(),
    )


@app.get("/admin/orders", response_model=list[OrderRead])
def admin_list_orders(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.payment),
            selectinload(Order.invoice),
            selectinload(Order.status_history),
        )
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_order_response(db, order) for order in orders]


@app.get("/admin/analytics", response_model=AdminAnalytics)
def admin_analytics(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    start_day = datetime.utcnow().date() - timedelta(days=13)
    daily_rows = (
        db.query(func.date(Order.created_at), func.count(Order.id))
        .filter(func.date(Order.created_at) >= start_day)
        .group_by(func.date(Order.created_at))
        .all()
    )
    daily_counts = {str(day): count for day, count in daily_rows}
    daily_orders = [
        {"date": (start_day + timedelta(days=offset)).isoformat(),
         "orders": int(daily_counts.get((start_day + timedelta(days=offset)).isoformat(), 0))}
        for offset in range(14)
    ]

    product_rows = (
        db.query(
            Product.name,
            Product.category,
            Product.gender,
            func.coalesce(func.sum(case((Order.id.is_not(None), OrderItem.quantity), else_=0)), 0),
            func.count(func.distinct(case((Order.id.is_not(None), OrderItem.order_id), else_=None))),
            func.coalesce(func.sum(case((Order.id.is_not(None), OrderItem.unit_price * OrderItem.quantity), else_=0)), 0),
        )
        .outerjoin(ProductVariant, ProductVariant.product_id == Product.id)
        .outerjoin(OrderItem, OrderItem.variant_id == ProductVariant.id)
        .outerjoin(
            Order,
            (Order.id == OrderItem.order_id)
            & Order.status.notin_(["cancelled", "payment_failed"])
            & Order.payment_status.notin_(["failed", "cancelled", "refunded"]),
        )
        .group_by(Product.name, Product.category, Product.gender)
        .all()
    )
    product_stats = [
        AdminProductStat(
            name=name,
            category=category,
            gender=gender,
            units_sold=int(units_sold),
            order_count=int(order_count),
            revenue=float(revenue),
        )
        for name, category, gender, units_sold, order_count, revenue in product_rows
    ]
    product_stats.sort(key=lambda item: (-item.units_sold, item.name.casefold()))

    category_rows = (
        db.query(Product.category, func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.status.notin_(["cancelled", "payment_failed"]),
            Order.payment_status.notin_(["failed", "cancelled", "refunded"]),
        )
        .group_by(Product.category)
        .all()
    )
    gender_rows = (
        db.query(Product.gender, func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.status.notin_(["cancelled", "payment_failed"]),
            Order.payment_status.notin_(["failed", "cancelled", "refunded"]),
        )
        .group_by(Product.gender)
        .all()
    )
    status_rows = (
        db.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    return AdminAnalytics(
        daily_orders=daily_orders,
        top_products=product_stats[:10],
        slow_products=list(reversed(product_stats[-10:])),
        category_sales=[{"category": category, "units_sold": int(units)} for category, units in category_rows],
        gender_sales=[{"gender": gender, "units_sold": int(units)} for gender, units in gender_rows],
        order_statuses=[{"status": name, "count": int(count)} for name, count in status_rows],
    )


@app.get("/admin/system-health", response_model=SystemHealth)
def admin_system_health(
    current_user: User = Depends(get_current_admin_user),
):
    return SystemHealth(**request_telemetry.snapshot())


@app.get("/admin/email-logs", response_model=list[EmailLogRead])
def admin_email_logs(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    return [
        EmailLogRead(
            id=email.id,
            recipient=email.recipient,
            subject=email.subject,
            event_type=email.event_type,
            status=email.status,
            error_message=email.error_message,
            created_at=email.created_at.isoformat(),
        )
        for email in db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(100).all()
    ]


@app.post("/admin/orders/{order_id}/cash-payment", response_model=OrderRead)
def confirm_cash_payment(
    order_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.payment_method != "Cash at store":
        raise HTTPException(status_code=400, detail="This order is not a cash-at-store order.")
    if order.status != "awaiting_payment":
        raise HTTPException(status_code=409, detail="This order is no longer waiting for cashier payment.")
    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail="Cash payment is not pending.")
    payment.status = "paid"
    payment.amount = _money(order.total_amount)
    order.payment_status = "paid"
    _add_status(db, order, "processing", "The store confirmed cash payment. The order is ready to be prepared.")
    db.add(PaymentEvent(payment_id=payment.id, event_type="cashier_confirmed", message=f"Cash payment confirmed by {current_user.email}."))
    _notify(db, order.user_id, "Cash payment confirmed", f"Payment for {order.order_number} was recorded by the store.")
    db.commit()
    send_order_email(
        order.id,
        "payment_confirmed",
        f"Payment confirmed: {order.order_number}",
        f"The store confirmed cash payment for order {order.order_number}. The order is ready to be prepared.",
    )
    return _order_response(db, order)


@app.patch("/admin/orders/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: int,
    payload: OrderStatusRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    transitions = {
        "processing": {"preparing"},
        "preparing": {
            "ready_for_pickup" if order.fulfillment_method == "pickup" else "out_for_delivery"
        },
        "ready_for_pickup": {"picked_up"},
        "out_for_delivery": {"delivered"},
    }
    if payload.status not in transitions.get(order.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move an order from '{order.status}' to '{payload.status}'.",
        )
    if order.payment_status != "paid":
        raise HTTPException(status_code=409, detail="Confirm payment before fulfillment begins.")
    note = payload.note or f"Order status updated to {payload.status.replace('_', ' ')}."
    _add_status(db, order, payload.status, note)
    _notify(db, order.user_id, "Order update", f"{order.order_number}: {note}")
    db.commit()
    send_order_email(
        order.id,
        "order_status",
        f"Order update: {order.order_number}",
        note,
    )
    return _order_response(db, order)
