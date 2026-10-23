"""Upgrade legacy demo databases and add query indexes.

Revision ID: 14c44b620dcf
Revises: 8dbf95ebc82b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "14c44b620dcf"
down_revision: Union[str, None] = "8dbf95ebc82b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("email_logs"):
        op.create_table(
            "email_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("recipient", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_email_logs_event_type", "email_logs", ["event_type"])
        op.create_index("ix_email_logs_id", "email_logs", ["id"])
        op.create_index("ix_email_logs_recipient", "email_logs", ["recipient"])

    additive_columns = {
        "products": {
            "gender": sa.Column(
                "gender", sa.String(length=20), nullable=False, server_default="unisex"
            ),
        },
        "student_profiles": {
            "class_id": sa.Column("class_id", sa.Integer(), nullable=True),
            "roll_number": sa.Column("roll_number", sa.String(length=30), nullable=True),
            "verified_at": sa.Column("verified_at", sa.DateTime(), nullable=True),
        },
        "orders": {
            "payment_status": sa.Column(
                "payment_status",
                sa.String(length=50),
                nullable=False,
                server_default="pending",
            ),
            "fulfillment_method": sa.Column(
                "fulfillment_method",
                sa.String(length=50),
                nullable=False,
                server_default="delivery",
            ),
            "estimated_ready_at": sa.Column(
                "estimated_ready_at", sa.DateTime(), nullable=True
            ),
            "subtotal": sa.Column(
                "subtotal",
                sa.Numeric(precision=10, scale=2),
                nullable=False,
                server_default="0",
            ),
            "tax_amount": sa.Column(
                "tax_amount",
                sa.Numeric(precision=10, scale=2),
                nullable=False,
                server_default="0",
            ),
            "delivery_fee": sa.Column(
                "delivery_fee",
                sa.Numeric(precision=10, scale=2),
                nullable=False,
                server_default="0",
            ),
        },
    }

    for table_name, columns in additive_columns.items():
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column_name, column in columns.items():
            if column_name not in existing_columns:
                op.add_column(table_name, column)

    indexes = (
        ("orders", "ix_orders_user_created_id", ["user_id", "created_at", "id"]),
        ("orders", "ix_orders_created_id", ["created_at", "id"]),
        (
            "order_status_history",
            "ix_order_status_history_order_created_id",
            ["order_id", "created_at", "id"],
        ),
        ("order_items", "ix_order_items_order_id", ["order_id"]),
        ("order_items", "ix_order_items_variant_id", ["variant_id"]),
    )
    for table_name, index_name, columns in indexes:
        if not sa.inspect(bind).has_index(table_name, index_name):
            op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    pass
