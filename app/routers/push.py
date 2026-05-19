from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import get_db, get_current_user
from app.models import User
from app.services.push_service import send_push_to_user

router = APIRouter(prefix="/push", tags=["Push"])

class TestPushRequest(BaseModel):
    event_type: str

@router.post("/test")
async def test_push(
    data: TestPushRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await send_push_to_user(current_user.id, data.event_type, db)
    return {"status": "ok", "event_type": data.event_type}
