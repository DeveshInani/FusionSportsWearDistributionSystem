from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.models import (
    Cart,
    Notification,
    Product,
    ProductVariant,
    School,
    SchoolCatalogItem,
    SchoolClass,
    StudentRoster,
    StudentProfile,
    User,
)


def _create_school(db: Session, name: str, city: str, description: str, logo_url: str) -> School:
    school = db.query(School).filter(School.name == name).first()
    if school:
        return school

    school = School(name=name, city=city, description=description, logo_url=logo_url)
    db.add(school)
    db.flush()

    for grade in range(1, 13 if "Greenfield" in name else 11):
        for section in ["A", "B", "C"][:2 if "Greenfield" in name else 3]:
            db.add(SchoolClass(school_id=school.id, grade=grade, section=section))

    return school


def _ensure_school_classes(db: Session, school: School):
    max_grade = 12 if "Greenfield" in school.name else 10
    sections = ["A", "B"] if "Greenfield" in school.name else ["A", "B", "C"]
    existing = {
        (item.grade, item.section)
        for item in db.query(SchoolClass).filter(SchoolClass.school_id == school.id).all()
    }
    for grade in range(1, max_grade + 1):
        for section in sections:
            if (grade, section) not in existing:
                db.add(SchoolClass(school_id=school.id, grade=grade, section=section))
    db.flush()


def _ensure_demo_roster(db: Session, schools: list[School]):
    roster_rows = [
        (schools[0], 8, "A", "G8-A-001", "Sam Student"),
        (schools[0], 8, "A", "G8-A-014", "Aarav Mehta"),
        (schools[0], 4, "B", "G4-B-022", "Anaya Rao"),
        (schools[1], 6, "B", "G6-B-009", "Mira Rao"),
        (schools[1], 3, "A", "G3-A-018", "Kabir Shah"),
    ]
    for school, grade, section, roll_number, student_name in roster_rows:
        school_class = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.school_id == school.id,
                SchoolClass.grade == grade,
                SchoolClass.section == section,
            )
            .first()
        )
        roster_entry = (
            db.query(StudentRoster)
            .filter(
                StudentRoster.school_id == school.id,
                StudentRoster.roll_number == roll_number,
            )
            .first()
        )
        if not roster_entry:
            db.add(
                StudentRoster(
                    school_id=school.id,
                    class_id=school_class.id,
                    section=section,
                    roll_number=roll_number,
                    student_name=student_name,
                    is_claimed=student_name == "Sam Student",
                )
            )


def _ensure_demo_accessories(db: Session, schools: list[School]):
    accessories = [
        _ensure_product(
            db,
            "School Tie",
            "Accessories",
            "School-color striped tie with an adjustable fit.",
            "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=800&q=80",
            [("Regular", "Navy stripe", 30, 399), ("Junior", "Navy stripe", 24, 349)],
        ),
        _ensure_product(
            db,
            "Uniform Belt",
            "Accessories",
            "Durable everyday belt with a simple school-approved buckle.",
            "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80",
            [("S", "Black", 25, 499), ("M", "Black", 22, 549), ("L", "Black", 18, 599)],
        ),
    ]
    for product in accessories:
        for school in schools:
            for variant in product.variants:
                catalog_item = (
                    db.query(SchoolCatalogItem)
                    .filter(
                        SchoolCatalogItem.school_id == school.id,
                        SchoolCatalogItem.variant_id == variant.id,
                    )
                    .first()
                )
                if not catalog_item:
                    db.add(
                        SchoolCatalogItem(
                            school_id=school.id,
                            variant_id=variant.id,
                            selling_price=variant.base_price,
                            stock_quantity=variant.stock_quantity,
                            is_active=True,
                        )
                    )


def _ensure_product(
    db: Session,
    name: str,
    category: str,
    description: str,
    image_url: str,
    variants: list[tuple[str, str, int, float]],
    gender: str = "unisex",
) -> Product:
    product = db.query(Product).filter(Product.name == name).first()
    if product:
        product.gender = gender
        return product

    product = Product(name=name, category=category, gender=gender, description=description, image_url=image_url)
    db.add(product)
    db.flush()

    for size, color, stock, price in variants:
        db.add(
            ProductVariant(
                product_id=product.id,
                size=size,
                color=color,
                stock_quantity=stock,
                base_price=price,
                is_active=True,
            )
        )
    return product


def seed_demo_data(db: Session):
    if db.query(School).count() > 0:
        schools = (
            db.query(School)
            .filter(
                School.name.in_(
                    ["Greenfield International School", "Sunrise Public School"]
                )
            )
            .order_by(School.id)
            .all()
        )
        for school in schools:
            _ensure_school_classes(db, school)
        if len(schools) >= 2:
            _ensure_demo_roster(db, schools)
            _ensure_demo_accessories(db, schools)
            for name, gender in {
                "Formal Blazer": "boys",
                "Classic Shirt": "boys",
                "Plaid Skirt": "girls",
                "Sports Tee": "unisex",
                "Pleated Trousers": "boys",
                "School Tie": "unisex",
                "Uniform Belt": "unisex",
            }.items():
                product = db.query(Product).filter(Product.name == name).first()
                if product:
                    product.gender = gender
            student = db.query(User).filter(User.email == "student@schooldemo.com").first()
            if student:
                profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
                school_class = (
                    db.query(SchoolClass)
                    .filter(
                        SchoolClass.school_id == schools[0].id,
                        SchoolClass.grade == 8,
                        SchoolClass.section == "A",
                    )
                    .first()
                )
                if profile:
                    profile.class_id = school_class.id
                    profile.roll_number = "G8-A-001"
                    profile.verified_at = profile.verified_at or datetime.utcnow()
                roster_entry = (
                    db.query(StudentRoster)
                    .filter(
                        StudentRoster.school_id == schools[0].id,
                        StudentRoster.roll_number == "G8-A-001",
                    )
                    .first()
                )
                if roster_entry:
                    roster_entry.is_claimed = True
        db.commit()
        _ensure_bootstrap_admin(db)
        return

    greenfield = _create_school(
        db,
        "Greenfield International School",
        "Bengaluru",
        "Premium formal uniforms and identity-appropriate school apparel for students from grades 1 to 12.",
        "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80",
    )
    sunrise = _create_school(
        db,
        "Sunrise Public School",
        "Hyderabad",
        "Colorful, comfortable everyday uniforms and sportswear tailored for active school life.",
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=800&q=80",
    )
    _ensure_school_classes(db, greenfield)
    _ensure_school_classes(db, sunrise)
    _ensure_demo_roster(db, [greenfield, sunrise])

    blazer = _ensure_product(
        db,
        "Formal Blazer",
        "Formal Uniform",
        "Tailored school blazer with embroidered crest and premium lining.",
        "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80",
        [("M", "Navy", 20, 1799), ("L", "Navy", 18, 1799), ("XL", "Navy", 10, 1899)],
        "boys",
    )
    shirt = _ensure_product(
        db,
        "Classic Shirt",
        "Formal Uniform",
        "Cotton-poly blend formal shirt with a clean fit for daily wear.",
        "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=800&q=80",
        [("28", "White", 40, 699), ("30", "White", 32, 699), ("32", "White", 24, 749)],
        "boys",
    )
    skirt = _ensure_product(
        db,
        "Plaid Skirt",
        "Girls Uniform",
        "School-approved pleated skirt in a neat plaid finish.",
        "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=800&q=80",
        [("S", "Plaid", 18, 1299), ("M", "Plaid", 26, 1299), ("L", "Plaid", 20, 1399)],
        "girls",
    )
    tee = _ensure_product(
        db,
        "Sports Tee",
        "Sportswear",
        "Lightweight breathable sports tee for PE and outdoor activities.",
        "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=800&q=80",
        [("S", "Royal Blue", 30, 899), ("M", "Royal Blue", 24, 899), ("L", "Royal Blue", 18, 949)],
        "unisex",
    )
    trouser = _ensure_product(
        db,
        "Pleated Trousers",
        "Formal Uniform",
        "Durable school trousers with flexible comfort and a neat finish.",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
        [("26", "Charcoal", 22, 1299), ("28", "Charcoal", 20, 1299), ("30", "Charcoal", 18, 1399)],
        "boys",
    )
    tie = _ensure_product(
        db,
        "School Tie",
        "Accessories",
        "School-color striped tie with an adjustable fit.",
        "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=800&q=80",
        [("Regular", "Navy stripe", 30, 399), ("Junior", "Navy stripe", 24, 349)],
    )
    belt = _ensure_product(
        db,
        "Uniform Belt",
        "Accessories",
        "Durable everyday belt with a simple school-approved buckle.",
        "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80",
        [("S", "Black", 25, 499), ("M", "Black", 22, 549), ("L", "Black", 18, 599)],
    )

    for product in [blazer, shirt, skirt, tee, trouser, tie, belt]:
        for variant in product.variants:
            db.add(
                SchoolCatalogItem(
                    school_id=greenfield.id,
                    variant_id=variant.id,
                    selling_price=variant.base_price,
                    stock_quantity=variant.stock_quantity,
                    is_active=True,
                )
            )
            db.add(
                SchoolCatalogItem(
                    school_id=sunrise.id,
                    variant_id=variant.id,
                    selling_price=max(float(variant.base_price) * 0.96, 599),
                    stock_quantity=variant.stock_quantity,
                    is_active=True,
                )
            )

    student = db.query(User).filter(User.email == "student@schooldemo.com").first()
    if not student:
        student = User(
            email="student@schooldemo.com",
            name="Sam Student",
            password_hash=hash_password("student123"),
            role="student",
            school_id=greenfield.id,
        )
        db.add(student)
        db.flush()

    if not db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first():
        school_class = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.school_id == greenfield.id,
                SchoolClass.grade == 8,
                SchoolClass.section == "A",
            )
            .first()
        )
        db.add(
            StudentProfile(
                user_id=student.id,
                school_id=greenfield.id,
                grade=8,
                section="A",
                class_id=school_class.id,
                roll_number="G8-A-001",
                verified_at=datetime.utcnow(),
            )
        )
    else:
        student_profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == student.id)
            .first()
        )
        student_profile.class_id = (
            db.query(SchoolClass)
            .filter(
                SchoolClass.school_id == greenfield.id,
                SchoolClass.grade == 8,
                SchoolClass.section == "A",
            )
            .first()
            .id
        )
        student_profile.roll_number = "G8-A-001"
        student_profile.verified_at = student_profile.verified_at or datetime.utcnow()

    cart = db.query(Cart).filter(Cart.user_id == student.id).first()
    if not cart:
        db.add(Cart(user_id=student.id, school_id=greenfield.id))

    if db.query(Notification).filter(Notification.user_id == student.id).count() == 0:
        db.add(
            Notification(
                user_id=student.id,
                title="Order confirmed",
                body="Your school uniform order has been confirmed and will ship within 3-5 business days.",
            )
        )

    db.commit()
    _ensure_bootstrap_admin(db)


def _ensure_bootstrap_admin(db: Session):
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return
    admin = db.query(User).filter(User.email == settings.BOOTSTRAP_ADMIN_EMAIL.lower()).first()
    if admin is None:
        admin = User(
            email=settings.BOOTSTRAP_ADMIN_EMAIL.lower(),
            name="Store Administrator",
            password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            role="admin",
        )
        db.add(admin)
    else:
        admin.role = "admin"
        admin.password_hash = hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD)
    db.commit()
