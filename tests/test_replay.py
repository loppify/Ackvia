from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    DeliveryAttempt,
    DeliveryAttemptResult,
    DeliveryStatus,
    DeliveryTrigger,
    WorkspaceRole,
)
from app.services.delivery import (
    DeliveryNotFoundError,
    DeliveryNotReplayableError,
    claim_next_delivery,
    process_delivery,
    queue_manual_replay,
)
from tests.conftest import (
    create_authenticated_workspace,
    create_delivery,
    create_membership,
    create_user,
    create_workspace,
)


@pytest.mark.asyncio
async def test_failed_delivery_can_be_queued_for_manual_replay(
    db: AsyncSession,
):
    user = await create_user(db)
    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.MEMBER,
    )

    delivery = await create_delivery(
        db,
        DeliveryStatus.FAILED,
        workspace=workspace,
    )

    delivery.attempt_count = 5
    delivery.next_retry_at = datetime.now(timezone.utc)

    await db.flush()

    result = await queue_manual_replay(
        db,
        delivery.id,
        user.id,
    )

    assert result.status == DeliveryStatus.PENDING
    assert result.queued_trigger == DeliveryTrigger.MANUAL_REPLAY
    assert result.failure_type is None

    # Replay starts a new processing cycle,
    # but does not rewrite attempt history.
    assert result.attempt_count == 5
    assert result.next_retry_at is None
    assert result.processing_started_at is None


@pytest.mark.asyncio
async def test_unknown_delivery_can_be_queued_for_manual_replay(
    db: AsyncSession,
):
    user = await create_user(db)
    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.OWNER,
    )

    delivery = await create_delivery(
        db,
        DeliveryStatus.UNKNOWN,
        workspace=workspace,
    )

    result = await queue_manual_replay(
        db,
        delivery.id,
        user.id,
    )

    assert result.status == DeliveryStatus.PENDING
    assert result.queued_trigger == DeliveryTrigger.MANUAL_REPLAY
    assert result.failure_type is None
    assert result.next_retry_at is None
    assert result.processing_started_at is None


@pytest.mark.asyncio
async def test_manual_replay_raises_not_found_for_missing_delivery(
    db: AsyncSession,
):
    user = await create_user(db)

    with pytest.raises(DeliveryNotFoundError):
        await queue_manual_replay(
            db,
            999999,
            user.id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        DeliveryStatus.PENDING,
        DeliveryStatus.PROCESSING,
        DeliveryStatus.AWAITING_RETRY,
        DeliveryStatus.SUCCEEDED,
    ],
)
async def test_manual_replay_rejects_non_replayable_status(
    db: AsyncSession,
    status: DeliveryStatus,
):
    user = await create_user(db)
    workspace = await create_workspace(db)

    await create_membership(
        db,
        user=user,
        workspace=workspace,
        role=WorkspaceRole.MEMBER,
    )

    delivery = await create_delivery(
        db,
        status,
        workspace=workspace,
    )

    with pytest.raises(DeliveryNotReplayableError):
        await queue_manual_replay(
            db,
            delivery.id,
            user.id,
        )


@pytest.mark.asyncio
async def test_replay_failed_delivery_endpoint(client, db: AsyncSession):
    user, workspace = await create_authenticated_workspace(client, db)

    delivery = await create_delivery(
        db,
        DeliveryStatus.FAILED,
        workspace=workspace,
    )

    response = await client.post(f"/api/deliveries/{delivery.id}/replay")

    assert response.status_code == 202
    assert response.json()["status"] == DeliveryStatus.PENDING.value


@pytest.mark.asyncio
async def test_replay_missing_delivery_returns_404(client, db: AsyncSession):
    await create_authenticated_workspace(client, db)

    response = await client.post("/api/deliveries/999999/replay")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manual_replay_is_recorded_in_attempt_history(
    client,
    db: AsyncSession,
    monkeypatch,
):
    user, workspace = await create_authenticated_workspace(client, db)

    delivery = await create_delivery(
        db,
        DeliveryStatus.FAILED,
        workspace=workspace,
    )

    response = await client.post(f"/api/deliveries/{delivery.id}/replay")
    assert response.status_code == 202

    db.expire_all()
    claimed = await claim_next_delivery(db)
    assert claimed.queued_trigger == DeliveryTrigger.MANUAL_REPLAY

    async def fake_execute_delivery_attempt(destination, message):
        return {"success": True, "external_reference": "manual-replay-test"}

    monkeypatch.setattr(
        "app.services.delivery.execute_delivery_attempt",
        fake_execute_delivery_attempt,
    )

    await process_delivery(delivery.id, db)

    attempt = await db.scalar(
        select(DeliveryAttempt).where(DeliveryAttempt.delivery_id == delivery.id)
    )

    assert attempt.trigger == DeliveryTrigger.MANUAL_REPLAY
    assert attempt.result == DeliveryAttemptResult.SUCCEEDED


@pytest.mark.asyncio
async def test_manual_replay_rejects_delivery_from_inaccessible_workspace(
    db: AsyncSession,
):
    user = await create_user(db)

    foreign_workspace = await create_workspace(
        db,
        name="Foreign Workspace",
    )

    delivery = await create_delivery(
        db,
        DeliveryStatus.FAILED,
        workspace=foreign_workspace,
    )

    with pytest.raises(DeliveryNotFoundError):
        await queue_manual_replay(
            db,
            delivery.id,
            user.id,
        )

    await db.refresh(delivery)

    assert delivery.status == DeliveryStatus.FAILED
    assert delivery.failure_type is not None


@pytest.mark.asyncio
async def test_manual_replay_membership_in_other_workspace_does_not_grant_access(
    db: AsyncSession,
):
    user = await create_user(db)

    accessible_workspace = await create_workspace(
        db,
        name="Accessible",
    )
    foreign_workspace = await create_workspace(
        db,
        name="Foreign",
    )

    await create_membership(
        db,
        user=user,
        workspace=accessible_workspace,
        role=WorkspaceRole.OWNER,
    )

    delivery = await create_delivery(
        db,
        DeliveryStatus.FAILED,
        workspace=foreign_workspace,
    )

    with pytest.raises(DeliveryNotFoundError):
        await queue_manual_replay(
            db,
            delivery.id,
            user.id,
        )
