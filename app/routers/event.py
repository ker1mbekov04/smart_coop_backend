from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import get_current_user, get_db
from app.models import User
from app.models.event_log import EventType
from app.schemas.event_log import EventsResponse, SeverityFilter
from app.schemas.history import PeriodValue
from app.services.event_log import events_get_service

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=EventsResponse)
async def get_events(
        period: PeriodValue = Query(default=PeriodValue.h24),
        severity: SeverityFilter = Query(default=SeverityFilter.all),
        event_type: EventType | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    return await events_get_service(period, severity, event_type, limit, offset, db)