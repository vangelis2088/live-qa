"""Moderator routes: view questions, mark them answered, delete them.

All routes require HTTP Basic auth (username ``admin``, password from the
``ADMIN_PASSWORD`` env var). If ``ADMIN_PASSWORD`` is unset or empty, every
request is denied.

CSRF: browsers resend Basic credentials automatically, so the state-changing
endpoints also require the ``HX-Request: true`` header (a custom header that a
cross-site form or simple fetch cannot send without a CORS preflight, which we
never allow) and reject requests whose ``Origin``/``Sec-Fetch-Site`` say they
came from another site.

Clickjacking: a click inside a framed copy of /moderate would pass the CSRF
checks above, so every response from these routes (errors included) carries
``X-Frame-Options: DENY`` and ``Content-Security-Policy: frame-ancestors
'none'`` via ``NoFrameRoute``.
"""

import os
import secrets
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db

ADMIN_USERNAME = "admin"
NO_FRAME_HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


class NoFrameRoute(APIRoute):
    """Route that adds anti-framing headers to every response, errors included."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def no_frame_handler(request: Request):
            try:
                response = await handler(request)
            except StarletteHTTPException as exc:
                response = await http_exception_handler(request, exc)
            except RequestValidationError as exc:
                response = await request_validation_exception_handler(request, exc)
            response.headers.update(NO_FRAME_HEADERS)
            return response

        return no_frame_handler


templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")
security = HTTPBasic(auto_error=False, realm="Live Q&A moderation")
router = APIRouter(route_class=NoFrameRoute)


def require_moderator(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> None:
    """Allow the request only with valid moderator Basic credentials."""
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Moderation is disabled."
        )
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials.",
        headers={"WWW-Authenticate": 'Basic realm="Live Q&A moderation"'},
    )
    if credentials is None:
        raise unauthorized
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), password.encode("utf-8")
    )
    if not (user_ok and password_ok):
        raise unauthorized


def require_same_origin_htmx(request: Request) -> None:
    """Reject state-changing requests that may be cross-site forgeries."""
    forbidden = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Cross-site request rejected."
    )
    if request.headers.get("hx-request") != "true":
        raise forbidden
    if request.headers.get("sec-fetch-site", "same-origin") not in (
        "same-origin",
        "none",
    ):
        raise forbidden
    origin = request.headers.get("origin")
    if origin is not None and urlsplit(origin).netloc != request.headers.get("host"):
        raise forbidden


def render_moderator_questions(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "_questions.html",
        {"questions": db.list_questions(), "voted": set(), "moderator": True},
    )


@router.get(
    "/moderate",
    response_class=HTMLResponse,
    dependencies=[Depends(require_moderator)],
)
def moderate_page(request: Request):
    return templates.TemplateResponse(
        request,
        "moderate.html",
        {"questions": db.list_questions(), "voted": set(), "moderator": True},
    )


@router.get(
    "/moderate/questions",
    response_class=HTMLResponse,
    dependencies=[Depends(require_moderator)],
)
def moderate_questions_partial(request: Request):
    return render_moderator_questions(request)


@router.post(
    "/moderate/questions/{question_id}/answered",
    response_class=HTMLResponse,
    dependencies=[Depends(require_moderator), Depends(require_same_origin_htmx)],
)
def mark_answered(request: Request, question_id: int):
    if not db.mark_answered(question_id):
        return HTMLResponse("Question not found.", status_code=404)
    return render_moderator_questions(request)


@router.delete(
    "/moderate/questions/{question_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_moderator), Depends(require_same_origin_htmx)],
)
def delete_question(request: Request, question_id: int):
    if not db.delete_question(question_id):
        return HTMLResponse("Question not found.", status_code=404)
    return render_moderator_questions(request)
