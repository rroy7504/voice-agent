from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import calls, ws
from app.services.event_bus import event_bus


def create_app() -> FastAPI:
    app = FastAPI(title="Insurance Co-Pilot", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(calls.router)
    app.include_router(ws.router)

    app.state.event_bus = event_bus

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
