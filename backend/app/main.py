from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.services.engine_service import initialize_engine_state, shutdown_engine
from backend.app.services.event_log import emit_event
from backend.app.services.history_ledger import initialize_history_ledger


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Minimal AI trading workstation scaffold.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    initialize_engine_state()
    initialize_history_ledger()
    emit_event(
        level="INFO",
        component="backend",
        message="Backend scaffold initialized.",
        data={
            "mode": settings.system_mode,
            "market_source": settings.kraken_market_source,
            "default_model": settings.default_llm_model,
        },
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    shutdown_engine()
