from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_game import router as game_router
from app.core.config import settings
from app.core.db import Base, engine
from app.models import game  # noqa: F401

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game_router)
