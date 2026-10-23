import os
import tempfile
import uuid
from io import BytesIO
from pathlib import Path

import pytest

_database_file = Path(tempfile.gettempdir()) / f"school-commerce-{uuid.uuid4().hex}.db"
_uploaded_image_files: list[Path] = []
os.environ["DATABASE_URL"] = f"sqlite:///{_database_file.as_posix()}"
os.environ["SECRET_KEY"] = "integration-test-key-that-is-not-used-outside-tests"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "store-admin@test.example"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "integration-test-admin-password"

from fastapi.testclient import TestClient
from PIL import Image

from app.db import SessionLocal, engine
from app.main import app
from app.seed import seed_demo_data


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    _database_file.unlink(missing_ok=True)
    for image_file in _uploaded_image_files:
        image_file.unlink(missing_ok=True)


def test_admin_to_student_delivery_and_fulfillment_flow(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post(
        "/admin/schools",
        json={"name": "Unauthorized School", "city": "Pune", "address": "Some Road", "classes": [{"grade": 1, "sections": ["A"]}]},
    ).status_code == 401

    admin_login = client.post(
        "/auth/login",
        json={"email": "store-admin@test.example", "password": "integration-test-admin-password"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    school_response = client.post(
        "/admin/schools",
        headers=admin_headers,
        json={
            "name": "Northside Academy",
            "city": "Pune",
            "address": "10 School Road, Pune",
            "description": "Student uniforms and sportswear.",
            "classes": [{"grade": 8, "sections": ["A", "B"]}],
        },
    )
    assert school_response.status_code == 201, school_response.text
    school_id = school_response.json()["id"]
    assert school_response.json()["address"] == "10 School Road, Pune"
    with SessionLocal() as db:
        seed_demo_data(db)
    assert client.get(f"/schools/{school_id}/classes").json() == [
        {"grade": 8, "sections": ["A", "B"]}
    ]
    assert client.get(
        f"/admin/schools/{school_id}/products",
        headers=admin_headers,
    ).json() == []

    roster_response = client.post(
        f"/admin/schools/{school_id}/roster",
        headers=admin_headers,
        json={"students": [{"name": "Aarav Mehta", "grade": 8, "section": "A", "roll_number": "N8-A-01"}]},
    )
    assert roster_response.status_code == 201
    assert roster_response.json()["created"] == 1
    duplicate_roster = client.post(
        f"/admin/schools/{school_id}/roster",
        headers=admin_headers,
        json={"students": [{"name": "Another Student", "grade": 8, "section": "A", "roll_number": "N8-A-01"}]},
    )
    assert duplicate_roster.status_code == 409
    invalid_class_roster = client.post(
        f"/admin/schools/{school_id}/roster",
        headers=admin_headers,
        json={"students": [{"name": "Wrong Class", "grade": 7, "section": "A", "roll_number": "N7-A-01"}]},
    )
    assert invalid_class_roster.status_code == 422

    image = BytesIO()
    Image.new("RGB", (32, 32), "navy").save(image, format="PNG")
    upload_response = client.post(
        "/admin/uploads/image",
        headers=admin_headers,
        files={"file": ("uniform.png", image.getvalue(), "image/png")},
    )
    assert upload_response.status_code == 200, upload_response.text
    image_url = upload_response.json()["image_url"]
    assert image_url.startswith("/api/media/")
    _uploaded_image_files.append(
        Path(__file__).resolve().parents[1] / "uploads" / image_url.rsplit("/", 1)[-1]
    )
    assert client.get(image_url.removeprefix("/api")).status_code == 200
    invalid_image = client.post(
        "/admin/uploads/image",
        headers=admin_headers,
        files={"file": ("fake.jpg", b"not an image", "image/jpeg")},
    )
    assert invalid_image.status_code == 415

    insecure_image_url = client.post(
        f"/admin/schools/{school_id}/products",
        headers=admin_headers,
        json={
            "name": "Unsafe Image Product",
            "category": "Sportswear",
            "gender": "unisex",
            "image_url": "http://example.test/untrusted.jpg",
            "variants": [{"size": "S", "price": 850, "stock_quantity": 1}],
        },
    )
    assert insecure_image_url.status_code == 422
    product_response = client.post(
        f"/admin/schools/{school_id}/products",
        headers=admin_headers,
        json={
            "name": "School Sports Shirt",
            "category": "Sportswear",
            "gender": "unisex",
            "description": "Quick-dry school team shirt.",
            "image_url": image_url,
            "variants": [
                {"size": "S", "color": "Navy", "price": 850, "stock_quantity": 2},
                {"size": "M", "color": "Navy", "price": 875, "stock_quantity": 0},
            ],
        },
    )
    assert product_response.status_code == 201, product_response.text
    catalog_items = product_response.json()
    available_item = next(item for item in catalog_items if item["size"] == "S")
    zero_stock_item = next(item for item in catalog_items if item["size"] == "M")

    student_registration = client.post(
        "/auth/register",
        json={
            "email": "aarav.northside@test.example",
            "password": "student-password-123",
            "name": "Aarav Mehta",
            "school_id": school_id,
            "grade": 8,
            "section": "A",
            "roll_number": "N8-A-01",
        },
    )
    assert student_registration.status_code == 201, student_registration.text
    invalid_registration = client.post(
        "/auth/register",
        json={
            "email": "wrong.student@test.example",
            "password": "student-password-123",
            "name": "Incorrect Roster Name",
            "school_id": school_id,
            "grade": 8,
            "section": "A",
            "roll_number": "N8-A-01",
        },
    )
    assert invalid_registration.status_code == 403
    student_token = student_registration.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    listed_schools = client.get("/schools").json()
    assert any(school["id"] == school_id for school in listed_schools)
    class_response = client.get(f"/schools/{school_id}/classes")
    assert class_response.status_code == 200
    assert {"grade": 8, "sections": ["A", "B"]} in class_response.json()
    products_response = client.get("/products", headers=student_headers)
    assert products_response.status_code == 200
    assert products_response.json()[0]["variants"][0]["catalog_item_id"] in {
        item["catalog_item_id"] for item in catalog_items
    }
    assert client.post(
        "/admin/schools",
        headers=student_headers,
        json={"name": "No Access School", "city": "Pune", "address": "Some Road", "classes": [{"grade": 1, "sections": ["A"]}]},
    ).status_code == 403
    assert client.post(
        "/cart/items",
        headers=student_headers,
        json={"catalog_item_id": zero_stock_item["catalog_item_id"], "quantity": 1},
    ).status_code == 409

    cart_response = client.post(
        "/cart/items",
        headers=student_headers,
        json={"catalog_item_id": available_item["catalog_item_id"], "quantity": 2},
    )
    assert cart_response.status_code == 200, cart_response.text
    too_many_response = client.post(
        "/cart/items",
        headers=student_headers,
        json={"catalog_item_id": available_item["catalog_item_id"], "quantity": 1},
    )
    assert too_many_response.status_code == 409

    missing_address = client.post(
        "/checkout",
        headers=student_headers,
        json={"payment_method": "upi", "fulfillment_method": "delivery"},
    )
    assert missing_address.status_code == 422
    partial_location = client.post(
        "/checkout",
        headers=student_headers,
        json={
            "payment_method": "upi",
            "fulfillment_method": "delivery",
            "delivery_address": "10 Lake View Road",
            "delivery_area": "Northside",
            "delivery_city": "Pune",
            "delivery_postal_code": "411001",
            "delivery_latitude": 18.52,
        },
    )
    assert partial_location.status_code == 422

    quote = client.post(
        "/checkout/quote",
        headers=student_headers,
        json={"fulfillment_method": "delivery"},
    )
    assert quote.status_code == 200
    assert quote.json()["delivery_fee"] > 0
    order_response = client.post(
        "/checkout",
        headers=student_headers,
        json={
            "payment_method": "upi",
            "fulfillment_method": "delivery",
            "delivery_address": "10 Lake View Road",
            "delivery_area": "Northside",
            "delivery_city": "Pune",
            "delivery_postal_code": "411001",
            "delivery_latitude": 18.52,
            "delivery_longitude": 73.86,
        },
    )
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()
    assert order["delivery_area"] == "Northside"
    assert order["delivery_latitude"] == pytest.approx(18.52)
    assert order["delivery_longitude"] == pytest.approx(73.86)

    edited_order_response = client.put(
        f"/orders/{order['id']}/items",
        headers=student_headers,
        json={"items": [{"catalog_item_id": available_item["catalog_item_id"], "quantity": 1}]},
    )
    assert edited_order_response.status_code == 200, edited_order_response.text
    order = edited_order_response.json()
    assert order["items"][0]["quantity"] == 1

    stock_after_reservation = client.get(
        f"/admin/schools/{school_id}/products",
        headers=admin_headers,
    ).json()
    assert next(item for item in stock_after_reservation if item["size"] == "S")["stock_quantity"] == 1

    failed_payment = client.post(
        f"/orders/{order['id']}/payment/simulate",
        headers=student_headers,
        json={"outcome": "failure"},
    )
    assert failed_payment.status_code == 200
    stock_after_failure = client.get(
        f"/admin/schools/{school_id}/products",
        headers=admin_headers,
    ).json()
    assert next(item for item in stock_after_failure if item["size"] == "S")["stock_quantity"] == 2
    successful_retry = client.post(
        f"/orders/{order['id']}/payment/simulate",
        headers=student_headers,
        json={"outcome": "success"},
    )
    assert successful_retry.status_code == 200
    assert successful_retry.json()["order_status"] == "processing"

    for next_status in ("preparing", "out_for_delivery", "delivered"):
        status_response = client.patch(
            f"/admin/orders/{order['id']}/status",
            headers=admin_headers,
            json={"status": next_status},
        )
        assert status_response.status_code == 200, status_response.text

    delivered_order = client.get(f"/orders/{order['id']}", headers=student_headers).json()
    assert delivered_order["status"] == "delivered"
    assert delivered_order["delivery_address"] == "10 Lake View Road"
    assert client.post(
        f"/orders/{order['id']}/cancel",
        headers=student_headers,
        json={"reason": "No longer needed"},
    ).status_code == 409

    inventory_update = client.patch(
        f"/admin/catalog-items/{available_item['catalog_item_id']}",
        headers=admin_headers,
        json={"selling_price": 900, "stock_quantity": 1, "is_active": True},
    )
    assert inventory_update.status_code == 200
    live_catalog = client.get("/products", headers=student_headers).json()
    live_variant = next(
        variant
        for product in live_catalog
        for variant in product["variants"]
        if variant["catalog_item_id"] == available_item["catalog_item_id"]
    )
    assert live_variant["price"] == pytest.approx(900)
    assert live_variant["stock_quantity"] == 1
    client.post(
        "/cart/items",
        headers=student_headers,
        json={"catalog_item_id": available_item["catalog_item_id"], "quantity": 1},
    ).raise_for_status()
    pickup_order_response = client.post(
        "/checkout",
        headers=student_headers,
        json={"payment_method": "cash", "fulfillment_method": "pickup"},
    )
    assert pickup_order_response.status_code == 201, pickup_order_response.text
    pickup_order = pickup_order_response.json()
    assert pickup_order["delivery_fee"] == 0
    assert pickup_order["delivery_address"] is None
    assert pickup_order["delivery_latitude"] is None
    cancelled_order = client.post(
        f"/orders/{pickup_order['id']}/cancel",
        headers=student_headers,
        json={"reason": "Pickup no longer required"},
    )
    assert cancelled_order.status_code == 200
    assert cancelled_order.json()["status"] == "cancelled"
    assert client.post(
        f"/orders/{pickup_order['id']}/cancel",
        headers=student_headers,
        json={"reason": "Try releasing stock again"},
    ).status_code == 409
    final_inventory = client.get(
        f"/admin/schools/{school_id}/products",
        headers=admin_headers,
    ).json()
    assert next(item for item in final_inventory if item["size"] == "S")["stock_quantity"] == 1
