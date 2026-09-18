from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.queries.deliveries import get_detailed_delivery_by_id
from app.database.session import get_db
from app.schemas.deliveries import DeliveryDetailRead
from app.services.delivery import manual_delivery, DeliveryNotFoundError, DeliveryNotReplayableError

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])


@router.get("/{delivery_id}", response_model=DeliveryDetailRead)
async def get_detailed_delivery(
        delivery_id: int,
        db: AsyncSession = Depends(get_db),
):
    res = await get_detailed_delivery_by_id(db, delivery_id)

    if res is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found",
        )

    return res


@router.post("/{delivery_id}/replay", response_model=DeliveryDetailRead, status_code=202)
async def replay_delivery(delivery_id: int, db: AsyncSession = Depends(get_db)):
    try:
        delivery = await manual_delivery(delivery_id, db)
    except DeliveryNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found"
        )
    except DeliveryNotReplayableError:
        raise HTTPException(
            status_code=409,
            detail="Delivery is not replayable"
        )
    return delivery
