from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Live Q&A", lifespan=lifespan)


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
            "max_text_len": db.MAX_TEXT_LEN,
            "max_author_len": db.MAX_AUTHOR_LEN,
        },
    )


@app.get("/questions", response_class=HTMLResponse)
def questions_partial(request: Request):
    return templates.TemplateResponse(
        request, "_questions.html", {"questions": db.list_questions()}
    )


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
    return questions_partial(request)
