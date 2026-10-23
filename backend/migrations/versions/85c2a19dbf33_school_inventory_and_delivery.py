"""Add school inventory, school addresses, and order delivery details.

Revision ID: 85c2a19dbf33
Revises: 14c44b620dcf
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "85c2a19dbf33"
down_revision: Union[str, None] = "14c44b620dcf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("address", sa.Text(), nullable=True))
    op.add_column(
        "school_catalog_items",
        sa.Column(
            "stock_quantity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("orders", sa.Column("delivery_address", sa.Text(), nullable=True))
    op.add_column(
        "orders", sa.Column("delivery_area", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("delivery_city", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("delivery_postal_code", sa.String(length=20), nullable=True)
    )
    op.add_column("orders", sa.Column("delivery_latitude", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("delivery_longitude", sa.Float(), nullable=True))
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.add_column(sa.Column("catalog_item_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_order_items_catalog_item_id",
            "school_catalog_items",
            ["catalog_item_id"],
            ["id"],
        )

    bind = op.get_bind()
    catalog = sa.table(
        "school_catalog_items",
        sa.column("id", sa.Integer()),
        sa.column("variant_id", sa.Integer()),
        sa.column("stock_quantity", sa.Integer()),
    )
    variants = sa.table(
        "product_variants",
        sa.column("id", sa.Integer()),
        sa.column("stock_quantity", sa.Integer()),
    )
    catalog_rows = bind.execute(
        sa.select(catalog.c.id, catalog.c.variant_id).order_by(catalog.c.id)
    )
    catalog_ids_by_variant: dict[int, list[int]] = {}
    for catalog_id, variant_id in catalog_rows:
        catalog_ids_by_variant.setdefault(variant_id, []).append(catalog_id)
    for variant_id, catalog_ids in catalog_ids_by_variant.items():
        legacy_stock = bind.execute(
            sa.select(variants.c.stock_quantity).where(variants.c.id == variant_id)
        ).scalar_one()
        stock_per_school, remainder = divmod(legacy_stock, len(catalog_ids))
        for index, catalog_id in enumerate(catalog_ids):
            extra_stock = 1 if index < remainder else 0
            bind.execute(
                sa.update(catalog)
                .where(catalog.c.id == catalog_id)
                .values(stock_quantity=stock_per_school + extra_stock)
            )

    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )
    order_items = sa.table(
        "order_items",
        sa.column("id", sa.Integer()),
        sa.column("order_id", sa.Integer()),
        sa.column("variant_id", sa.Integer()),
        sa.column("catalog_item_id", sa.Integer()),
    )
    catalog_lookup = sa.table(
        "school_catalog_items",
        sa.column("id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
        sa.column("variant_id", sa.Integer()),
    )
    items_to_backfill = bind.execute(
        sa.select(order_items.c.id, orders.c.school_id, order_items.c.variant_id)
        .select_from(order_items.join(orders, order_items.c.order_id == orders.c.id))
        .where(order_items.c.catalog_item_id.is_(None))
    )
    for item_id, school_id, variant_id in items_to_backfill:
        catalog_id = bind.execute(
            sa.select(catalog_lookup.c.id)
            .where(
                catalog_lookup.c.school_id == school_id,
                catalog_lookup.c.variant_id == variant_id,
            )
            .limit(1)
        ).scalar()
        if catalog_id is not None:
            bind.execute(
                sa.update(order_items)
                .where(order_items.c.id == item_id)
                .values(catalog_item_id=catalog_id)
            )


def downgrade() -> None:
    op.drop_column("order_items", "catalog_item_id")
    op.drop_column("orders", "delivery_longitude")
    op.drop_column("orders", "delivery_latitude")
    op.drop_column("orders", "delivery_postal_code")
    op.drop_column("orders", "delivery_city")
    op.drop_column("orders", "delivery_area")
    op.drop_column("orders", "delivery_address")
    op.drop_column("school_catalog_items", "stock_quantity")
    op.drop_column("schools", "address")
