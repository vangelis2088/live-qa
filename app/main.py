import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.templating import Jinja2Templates

from app import db

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    topics_file = os.environ.get("TOPICS_FILE", "data/topics.json")
    if Path(topics_file).is_file():
        db.load_organizer_topics(topics_file)
    yield


app = FastAPI(title="Voting App", lifespan=lifespan)


def _topics_response(
    request: Request, error: str | None = None, status_code: int = 200
):
    return templates.TemplateResponse(
        request,
        "_topics.html",
        {"topics": db.list_topics(), "error": error},
        status_code=status_code,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"topics": db.list_topics(), "error": None}
    )


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
