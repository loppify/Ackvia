"""initial schema

Revision ID: 0bc438ed7411
Revises:
Create Date: 2026-09-13 13:36:20.160941
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0bc438ed7411"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column(
            "language",
            sa.String(length=5),
            nullable=False,
            server_default="en",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "destinations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("form_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "submissions",
        sa.Column("form_id", sa.UUID(), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["form_id"],
            ["forms.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deliveries",
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SUCCEEDED",
                "FAILED",
                "UNKNOWN",
                "AWAITING_RETRY",
                "PROCESSING",
                name="deliverystatus",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "failure_type",
            sa.Enum(
                "PERMANENT",
                "RETRIES_EXHAUSTED",
                name="failuretype",
            ),
            nullable=True,
        ),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "external_reference",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "processing_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            """
            (status = 'FAILED' AND failure_type IS NOT NULL)
            OR
            (status != 'FAILED' AND failure_type IS NULL)
            """,
            name="ck_delivery_failure_type",
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["destinations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_id",
            "destination_id",
            name="uq_delivery_submission_destination",
        ),
    )

    op.create_table(
        "delivery_attempts",
        sa.Column("delivery_id", sa.Integer(), nullable=False),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "result",
            sa.Enum(
                "SUCCEEDED",
                "RETRYABLE_FAILURE",
                "PERMANENT_FAILURE",
                "UNKNOWN",
                name="deliveryattemptresult",
            ),
            nullable=True,
        ),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column(
            "trigger",
            sa.Enum(
                "AUTOMATIC",
                "RETRY",
                "MANUAL_REPLAY",
                name="deliverytrigger",
            ),
            nullable=False,
            server_default="AUTOMATIC",
        ),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["deliveries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("delivery_attempts")
    op.drop_table("deliveries")
    op.drop_table("submissions")
    op.drop_table("destinations")
    op.drop_table("forms")

    op.execute("DROP TYPE IF EXISTS deliverytrigger")
    op.execute("DROP TYPE IF EXISTS deliveryattemptresult")
    op.execute("DROP TYPE IF EXISTS failuretype")
    op.execute("DROP TYPE IF EXISTS deliverystatus")
