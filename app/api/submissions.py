from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database.models import User
from app.database.queries.submissions import get_accessible_submission_by_id
from app.database.session import get_db
from app.schemas.submissions import SubmissionRead

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.get("/{sub_id}", response_model=SubmissionRead)
async def get_detailed_submission(
    sub_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    detailed_submission = await get_accessible_submission_by_id(
        db=db, submission_id=sub_id, user_id=user.id
    )

    if detailed_submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )

    return detailed_submission
