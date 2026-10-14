import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app import db

VOTER_COOKIE = "voter_id"

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    topics_file = os.environ.get("TOPICS_FILE", "data/topics.json")
    if Path(topics_file).is_file():
        db.load_organizer_topics(topics_file)
    yield


app = FastAPI(title="Voting App", lifespan=lifespan)


def _voter(request: Request) -> tuple[str, bool]:
    """Return (voter_id, is_new); the cookie is only an identity key, never a count."""
    voter_id = request.cookies.get(VOTER_COOKIE, "")
    if len(voter_id) == 32 and all(c in "0123456789abcdef" for c in voter_id):
        return voter_id, False
    return uuid.uuid4().hex, True


def _render(
    request: Request,
    template: str,
    error: str | None = None,
    status_code: int = 200,
    voter: tuple[str, bool] | None = None,
):
    voter_id, is_new = voter or _voter(request)
    response = templates.TemplateResponse(
        request,
        template,
        {"topics": db.list_topics(voter_id), "error": error},
        status_code=status_code,
    )
    if is_new:
        response.set_cookie(
            VOTER_COOKIE,
            voter_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )
    return response


def _topics_response(
    request: Request, error: str | None = None, status_code: int = 200
):
    return _render(request, "_topics.html", error, status_code)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(request: Request):
    return _render(request, "index.html")


@app.get("/topics")
def topics(request: Request):
    return _topics_response(request)


@app.post("/topics")
def create_topic(request: Request, title: str = Form(""), author: str = Form("")):
    title = title.strip()
    if not title:
        return _topics_response(request, "Please enter a topic.", 422)
    if len(title) > db.MAX_TITLE_LEN:
        return _topics_response(
            request, f"Topic must be at most {db.MAX_TITLE_LEN} characters.", 422
        )
    db.add_topic(title, author.strip(), "attendee")
    return _topics_response(request)


@app.post("/topics/{topic_id}/vote")
def vote(request: Request, topic_id: int):
    voter = _voter(request)
    if not db.cast_vote(voter[0], topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return _render(request, "_topics.html", voter=voter)
