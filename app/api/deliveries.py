from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database.models import User
from app.database.queries.deliveries import get_accessible_delivery_by_id
from app.database.session import get_db
from app.schemas.deliveries import DeliveryDetailRead
from app.services.delivery import (
    DeliveryNotFoundError,
    DeliveryNotReplayableError,
    queue_manual_replay,
)

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])


@router.get("/{delivery_id}", response_model=DeliveryDetailRead)
async def get_detailed_delivery(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await get_accessible_delivery_by_id(db, delivery_id, user_id=user.id)

    if res is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    return res


@router.post(
    "/{delivery_id}/replay",
    response_model=DeliveryDetailRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def replay_delivery(
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        delivery = await queue_manual_replay(db, delivery_id, user.id)
    except DeliveryNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found"
        )
    except DeliveryNotReplayableError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Delivery is not replayable"
        )
    return delivery
