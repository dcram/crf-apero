"""Création de la table bookings

Revision ID: 0001
Revises:
Create Date: 2026-09-13
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tuesday", sa.Date, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("phone", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tuesday", name="uq_bookings_tuesday"),
    )


def downgrade() -> None:
    op.drop_table("bookings")
