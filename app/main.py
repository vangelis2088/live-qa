from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db
from app.export import router as export_router
from app.moderation import router as moderation_router

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Live Q&A", lifespan=lifespan)
app.include_router(moderation_router)
app.include_router(export_router)

VOTED_COOKIE = "voted"
VOTED_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def voted_ids(request: Request) -> set[int]:
    raw = request.cookies.get(VOTED_COOKIE, "")
    return {int(part) for part in raw.split(".") if part.isdigit()}


def render_questions(request: Request, voted: set[int] | None = None):
    if voted is None:
        voted = voted_ids(request)
    return templates.TemplateResponse(
        request,
        "_questions.html",
        {"questions": db.list_questions(), "voted": voted},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "questions": db.list_questions(),
            "voted": voted_ids(request),
            "max_text_len": db.MAX_TEXT_LEN,
            "max_author_len": db.MAX_AUTHOR_LEN,
        },
    )


@app.get("/questions", response_class=HTMLResponse)
def questions_partial(request: Request):
    return render_questions(request)


@app.post("/questions", response_class=HTMLResponse)
def create_question(request: Request, text: str = Form(""), author: str = Form("")):
    text = text.strip()
    author = author.strip()
    if not text:
        return HTMLResponse("Question text is required.", status_code=422)
    if len(text) > db.MAX_TEXT_LEN:
        return HTMLResponse(
            f"Question must be at most {db.MAX_TEXT_LEN} characters.", status_code=422
        )
    if len(author) > db.MAX_AUTHOR_LEN:
        return HTMLResponse(
            f"Name must be at most {db.MAX_AUTHOR_LEN} characters.", status_code=422
        )
    db.create_question(text, author or None)
    return render_questions(request)


@app.post("/questions/{question_id}/upvote", response_class=HTMLResponse)
def upvote_question(request: Request, question_id: int):
    voted = voted_ids(request)
    if question_id in voted:
        if not db.question_exists(question_id):
            return HTMLResponse("Question not found.", status_code=404)
        return render_questions(request, voted)
    if not db.upvote_question(question_id):
        return HTMLResponse("Question not found.", status_code=404)
    voted.add(question_id)
    response = render_questions(request, voted)
    response.set_cookie(
        VOTED_COOKIE,
        ".".join(str(i) for i in sorted(voted)),
        max_age=VOTED_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response
