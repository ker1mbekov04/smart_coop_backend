from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import verify_api_key, get_db, get_current_user
from app.models import User
from app.schemas.mode import ModeCurrentResponse, ModeCurrentRequest, ModeResponse, SetModeRequest, ModeHistoryResponse
from app.services.mode_service import mode_current_create_service, mode_current_get_service, mode_set_service, mode_history_service

router = APIRouter(prefix="/mode", tags=["Mode"])


@router.get("/current", response_model=ModeResponse)
async def mode_current_get(user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    return await mode_current_get_service(db)


@router.put("/set", response_model=ModeResponse)
async def mode_set(data: SetModeRequest,
                   user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    return await mode_set_service(data, db, user_id=user.id)


@router.post("/current", response_model=ModeCurrentResponse)
async def mode_current_create(data: ModeCurrentRequest,
                              _: User = Depends(verify_api_key),
                              db: AsyncSession = Depends(get_db)):
    return await mode_current_create_service(data, db)


@router.get("/history", response_model=ModeHistoryResponse)
async def mode_history(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    items, count = await mode_history_service(limit, offset, db)
    return ModeHistoryResponse(items=items, count=count)