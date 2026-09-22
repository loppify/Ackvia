from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.deliveries import router as deliveries_router
from app.api.forms import router as forms_router
from app.api.ingest import router as ingest_router
from app.api.submissions import router as submissions_router
from app.api.auth import router as auth_router
from app.core.i18n import (
    SUPPORTED_LANGUAGES,
    get_locale,
)
from app.services.telegram import http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await http_client.aclose()


app = FastAPI(title="Ackvia", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(forms_router)
app.include_router(ingest_router)
app.include_router(submissions_router)
app.include_router(deliveries_router)
app.include_router(auth_router)


@app.get("/", response_class=HTMLResponse)
async def render_index(
        request: Request, locale: Annotated[tuple[str, dict[str, str]], Depends(get_locale)]
):
    language, translations = locale

    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "language": language,
            "t": lambda key: translations.get(key, key),
        },
    )

    if request.query_params.get("lang") in SUPPORTED_LANGUAGES:
        response.set_cookie(
            key="language",
            value=language,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )

    return response


@app.get("/success", response_class=HTMLResponse)
async def render_success(
        request: Request, locale: Annotated[tuple[str, dict[str, str]], Depends(get_locale)]
):
    language, translations = locale

    response = templates.TemplateResponse(
        request=request,
        name="success.html",
        context={
            "language": language,
            "t": lambda key: translations.get(key, key),
        },
    )

    if request.query_params.get("lang") in SUPPORTED_LANGUAGES:
        response.set_cookie(
            key="language",
            value=language,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )

    return response
