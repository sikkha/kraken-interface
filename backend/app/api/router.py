from fastapi import APIRouter

from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.engine import router as engine_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.history import router as history_router
from backend.app.api.routes.market import router as market_router
from backend.app.api.routes.system import router as system_router
from backend.app.api.routes.trading import router as trading_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(market_router, tags=["market"])
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(system_router, tags=["system"])
api_router.include_router(trading_router, tags=["trading"])
api_router.include_router(engine_router, tags=["engine"])
api_router.include_router(history_router, tags=["history"])
