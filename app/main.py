from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routes import auth, datasets, health, rules, runs
from app.core.logging import setup_logging
from pathlib import Path

from fastapi.staticfiles import StaticFiles

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()  # only when the server really starts
    yield


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(title="DataGuard", version="1.0.0", lifespan=lifespan)
    register_error_handlers(app)
    for module in (health, auth, datasets, rules, runs):        app.include_router(module.router, prefix=API_PREFIX)
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()