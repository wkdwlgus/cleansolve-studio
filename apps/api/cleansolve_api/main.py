from fastapi import FastAPI

from .routes.jobs import router as jobs_router


app = FastAPI(title="CleanSolve Studio API")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router)
