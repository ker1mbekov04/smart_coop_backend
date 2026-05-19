from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import verify_api_key, get_db, get_current_user
from app.models import User
from app.schemas.mode import ModeCurrentResponse, ModeCurrentRequest, ModeResponse, SetModeRequest
from app.services.mode_service import mode_current_create_service, mode_current_get_service, mode_set_service

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