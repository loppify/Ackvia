import json
import uuid
from typing import Annotated, Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion import MAX_REQUEST_BODY_BYTES, validate_ingestion_payload
from app.database.queries.forms import get_form_with_destination
from app.database.queries.submissions import create_submission
from app.database.session import get_db
from app.exceptions import InvalidSubmissionPayloadError

router = APIRouter()


async def read_limited_body(request: Request) -> bytes:
    body = bytearray()

    async for chunk in request.stream():
        body.extend(chunk)

        if len(body) > MAX_REQUEST_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Request body too large",
            )

    return bytes(body)


async def parse_submission_request(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "application/json":
        body = await read_limited_body(request)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid JSON payload",
            )

        try:
            validate_ingestion_payload(data)
        except InvalidSubmissionPayloadError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid submission payload",
            )
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Form payload is empty"
            )
        return data
    elif (
        media_type == "application/x-www-form-urlencoded"
        # or "multipart/form-data" in content_type
    ):
        body = await read_limited_body(request)
        try:
            data = dict(parse_qsl(body.decode()))
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid submission payload",
            )
        try:
            validate_ingestion_payload(data)
        except InvalidSubmissionPayloadError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invalid submission payload",
            )
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Form payload is empty"
            )
        return data

    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type",
        )


@router.post("/f/{form_id}")
async def handle_form_submission(
    form_id: uuid.UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    data = await parse_submission_request(request)

    form_obj = await get_form_with_destination(db, form_id)

    if form_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form endpoint not found"
        )

    submission = await create_submission(db=db, form=form_obj, payload=data)

    accept = request.headers.get("accept", "")

    if "application/json" in accept:
        return JSONResponse(
            content={"status": "accepted", "id": submission.id},
            status_code=status.HTTP_202_ACCEPTED,
        )
    return RedirectResponse(url="/success", status_code=status.HTTP_303_SEE_OTHER)
