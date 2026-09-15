import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func, Index, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    AWAITING_RETRY = "awaiting_retry"
    PROCESSING = "processing"


class FailureType(str, enum.Enum):
    PERMANENT = "permanent"
    RETRIES_EXHAUSTED = "retries_exhausted"


class DeliveryAttemptResult(str, enum.Enum):
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    UNKNOWN = "unknown"


class DeliveryTrigger(str, enum.Enum):
    AUTOMATIC = "automatic"
    RETRY = "retry"
    MANUAL_REPLAY = "manual_replay"


class Base(DeclarativeBase):
    __abstract__ = True
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"


class Form(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="form", cascade="all, delete-orphan"
    )
    destinations: Mapped[list["Destination"]] = relationship(
        back_populates="form", cascade="all, delete-orphan"
    )


class Submission(Base):
    __table_args__ = (
        Index(
            "ix_submissions_form_id_created_at",
            "form_id",
            "created_at",
        ),
    )

    form_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    form: Mapped["Form"] = relationship(back_populates="submissions")
    deliveries: Mapped[list["Delivery"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan", lazy="raise"
    )


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint(
            "submission_id", "destination_id", name="uq_delivery_submission_destination"
        ),
        CheckConstraint(
            """
            (status = 'FAILED' AND failure_type IS NOT NULL)
            OR
            (status != 'FAILED' AND failure_type IS NULL)
            """,
            name="ck_delivery_failure_type",
        ),
        Index("ix_deliveries_destination_id", "destination_id"),
        Index(
            "ix_deliveries_awaiting_retry_next_retry_at",
            "next_retry_at",
            postgresql_where=(text("status = 'AWAITING_RETRY'")),
        ),

    )
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False
    )

    status: Mapped[DeliveryStatus] = mapped_column(
        nullable=False, default=DeliveryStatus.PENDING
    )
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_type: Mapped[FailureType | None] = mapped_column(default=None)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_reference: Mapped[str | None] = mapped_column(String(255))
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    submission: Mapped["Submission"] = relationship(back_populates="deliveries")
    destination: Mapped["Destination"] = relationship(
        lazy="selectin", back_populates="deliveries"
    )
    attempts: Mapped[list["DeliveryAttempt"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan", lazy="selectin"
    )


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (
        Index(
            "ix_delivery_attempts_delivery_id_created_at",
            "delivery_id",
            "created_at",
        ),
    )
    delivery_id: Mapped[int] = mapped_column(
        ForeignKey("deliveries.id", ondelete="CASCADE")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[DeliveryAttemptResult | None]
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger: Mapped[DeliveryTrigger] = mapped_column(default=DeliveryTrigger.AUTOMATIC)
    delivery: Mapped["Delivery"] = relationship(back_populates="attempts")


class Destination(Base):
    __table_args__ = (
        Index(
            "ix_destinations_form_id",
            "form_id",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    form_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)

    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    form: Mapped["Form"] = relationship(back_populates="destinations")
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="destination")
