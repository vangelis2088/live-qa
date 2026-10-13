from fastapi import FastAPI

app = FastAPI(title="Live Q&A")


@app.get("/health")
def health():
    return {"status": "ok"}