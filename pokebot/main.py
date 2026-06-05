"""Application FastAPI : initialise la base, seed, planificateur et routes."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from .database import init_db
from .scheduler import shutdown_scheduler, start_scheduler
from .seed import seed_defaults
from .utils.logging import setup_logging
from .web.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    seed_defaults()
    start_scheduler()
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="Bot-alertepk", version=__version__, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)
    return app


app = create_app()
