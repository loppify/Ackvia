from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.queries.deliveries import get_detailed_delivery_by_id
from app.database.session import get_db
from app.schemas.deliveries import DeliveryDetailRead

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
            detail="Submission not found",
        )

    return res
