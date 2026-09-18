from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Delivery


async def get_detailed_delivery_by_id(db: AsyncSession, delivery_id: int):
    return await db.scalar(
        select(Delivery)
        .where(Delivery.id == delivery_id)
        .options(selectinload(Delivery.attempts))
    )
