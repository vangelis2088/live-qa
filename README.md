# Live Q&A

A small FastAPI app where an audience submits questions and upvotes them live. Pages are server-rendered with Jinja2 and updated with htmx.

## API reference

| Method | Path | Parameters | Returns | Side effects |
| --- | --- | --- | --- | --- |
| GET | `/health` | none | JSON `{"status": "ok"}` | none |
| GET | `/` | none | Full HTML page (`index.html`) with the question list, the submit form and the max-length limits (280 chars for text, 50 for author) | none; reads the `voted` cookie to disable already-voted buttons |
| GET | `/questions` | none | htmx partial (`_questions.html`): the question list, ordered by votes, then newest first. The page polls it every 3 seconds | none; reads the `voted` cookie |
| POST | `/questions` | Form fields: `text` (required, trimmed, max 280 chars), `author` (optional, trimmed, max 50 chars; stored as anonymous when empty) | htmx partial (`_questions.html`) with the updated list. Validation failures return a plain-text body with status 422: empty text, text over 280 chars, or author over 50 chars | inserts a question into the database |
| POST | `/questions/{question_id}/upvote` | Path: `question_id` (int). No form fields | htmx partial (`_questions.html`) with the updated list. 404 with plain text `Question not found.` if the question does not exist | increments the question's vote count, once per browser. Sets the `voted` cookie (dot-separated list of voted ids, `HttpOnly`, `SameSite=Lax`, max age 1 year). A repeat vote on an already-voted question changes nothing and sets no cookie |
