import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.queries.forms import get_form_with_destination
from app.database.queries.submissions import create_submission
from app.database.session import get_db

router = APIRouter()


async def parse_submission_request(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("JSON payload must be an object")
            return data
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload"
            )
    elif (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        form_data = await request.form()
        return dict(form_data)
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type",
        )


@router.post("/f/{form_id}")
async def handle_form_submission(
    form_id: uuid.UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    form_obj = await get_form_with_destination(db, form_id)

    if form_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form endpoint not found"
        )

    data = await parse_submission_request(request)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Form payload is empty"
        )

    submission = await create_submission(db=db, form=form_obj, payload=data)

    accept = request.headers.get("accept", "")

    if "application/json" in accept:
        return JSONResponse(
            content={"status": "accepted", "id": submission.id},
            status_code=status.HTTP_202_ACCEPTED,
        )
    return RedirectResponse(url="/success", status_code=status.HTTP_303_SEE_OTHER)
