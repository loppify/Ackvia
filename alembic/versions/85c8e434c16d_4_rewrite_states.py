"""4-rewrite-states

Revision ID: 85c8e434c16d
Revises: 3d31aa2ddba6
Create Date: 2026-09-11 17:18:33.541956
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "85c8e434c16d"
down_revision: Union[str, Sequence[str], None] = "3d31aa2ddba6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

failure_type_enum = postgresql.ENUM(
    "PERMANENT",
    "RETRIES_EXHAUSTED",
    name="failuretype",
    create_type=False,
)

delivery_attempt_result_enum = postgresql.ENUM(
    "SUCCEEDED",
    "RETRYABLE_FAILURE",
    "PERMANENT_FAILURE",
    "UNKNOWN",
    name="deliveryattemptresult",
    create_type=False,
)

delivery_trigger_enum = postgresql.ENUM(
    "AUTOMATIC",
    "RETRY",
    "MANUAL_REPLAY",
    name="deliverytrigger",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("ALTER TYPE deliverystatus ADD VALUE IF NOT EXISTS 'PENDING'")
    op.execute("ALTER TYPE deliverystatus ADD VALUE IF NOT EXISTS 'UNKNOWN'")
    op.execute("ALTER TYPE deliverystatus ADD VALUE IF NOT EXISTS 'AWAITING_RETRY'")

    failure_type_enum.create(bind, checkfirst=True)
    delivery_attempt_result_enum.create(bind, checkfirst=True)
    delivery_trigger_enum.create(bind, checkfirst=True)

    op.create_table(
        "deliveryattempts",
        sa.Column("delivery_id", sa.Integer(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result",
            delivery_attempt_result_enum,
            nullable=True,
        ),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column(
            "trigger",
            delivery_trigger_enum,
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
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
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["deliverys.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "deliverys",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "deliverys",
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "deliverys",
        sa.Column(
            "failure_type",
            failure_type_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "deliverys",
        sa.Column(
            "last_error",
            sa.String(),
            nullable=True,
        ),
    )

    op.add_column(
        "deliverys",
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "deliverys",
        sa.Column(
            "external_reference",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE deliverys
        SET failure_type = 'PERMANENT'
        WHERE status = 'FAILED'
        """
    )

    op.create_unique_constraint(
        "uq_delivery_submission_destination",
        "deliverys",
        ["submission_id", "destination_id"],
    )

    op.create_check_constraint(
        "ck_delivery_failure_type",
        "deliverys",
        """
        (status = 'FAILED' AND failure_type IS NOT NULL)
        OR
        (status != 'FAILED' AND failure_type IS NULL)
        """,
    )

    op.alter_column(
        "deliverys",
        "attempt_count",
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(
        "ck_delivery_failure_type",
        "deliverys",
        type_="check",
    )

    op.drop_constraint(
        "uq_delivery_submission_destination",
        "deliverys",
        type_="unique",
    )

    op.drop_column("deliverys", "external_reference")
    op.drop_column("deliverys", "delivered_at")
    op.drop_column("deliverys", "last_error")
    op.drop_column("deliverys", "failure_type")
    op.drop_column("deliverys", "next_retry_at")
    op.drop_column("deliverys", "attempt_count")

    op.drop_table("deliveryattempts")

    delivery_trigger_enum.drop(bind, checkfirst=True)
    delivery_attempt_result_enum.drop(bind, checkfirst=True)
    failure_type_enum.drop(bind, checkfirst=True)
