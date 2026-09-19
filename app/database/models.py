import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
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


class WorkspaceRole(str, enum.Enum):
    OWNER = "owner"
    MEMBER = "member"


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
    __table_args__ = (
        Index(
            "ix_forms_workspace_id",
            "workspace_id",
        ),
    )
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
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    workspace: Mapped["Workspace"] = relationship(back_populates="forms")


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
    queued_trigger: Mapped[DeliveryTrigger] = mapped_column(
        nullable=False, default=DeliveryTrigger.AUTOMATIC
    )
    submission: Mapped["Submission"] = relationship(back_populates="deliveries")
    destination: Mapped["Destination"] = relationship(
        lazy="selectin", back_populates="deliveries"
    )
    attempts: Mapped[list["DeliveryAttempt"]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DeliveryAttempt.created_at",
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
    trigger: Mapped[DeliveryTrigger]
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


class Workspace(Base):
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(nullable=False)

    forms: Mapped[list["Form"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class User(Base):
    __table_args__ = (
        UniqueConstraint(
            "email", name="uq_users_email"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "workspace_id", name="uq_workspace_memberships_user_workspace"
        ),
        Index(
            "ix_workspace_memberships_workspace_id",
            "workspace_id"
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[WorkspaceRole] = mapped_column(nullable=False)
    workspace: Mapped["Workspace"] = relationship(
        back_populates="memberships"
    )
    user: Mapped["User"] = relationship(
        back_populates="memberships"
    )
