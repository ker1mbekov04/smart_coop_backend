from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.thresholds import ThresholdsResponse, ThresholdsUpdateRequest
from app.services.threshold_service import get_current_thresholds, thresholds_update_service

router = APIRouter(prefix="/thresholds", tags=["Thresholds"])


@router.get("", response_model=ThresholdsResponse)
async def thresholds_get(user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    return await get_current_thresholds(db)


@router.put("", response_model=ThresholdsResponse)
async def thresholds_update(data: ThresholdsUpdateRequest,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    return await thresholds_update_service(data, db)