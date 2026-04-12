from fastapi import APIRouter

from backend.app.schemas.system import SystemStatus
from backend.app.services.system_service import get_system_status


router = APIRouter()


@router.get("/system/state", response_model=SystemStatus)
def system_state() -> SystemStatus:
    return get_system_status()
