from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.dependencies import verify_api_key, get_db, get_current_user
from app.models import User
from app.models.device_command import CommandType
from app.schemas.command import (
    CommandStatusResponse, CommandAutoRequest, PendingCommandsResponse,
    CommandDoorResponse, CommandDoorRequest, CommandRelayRequest,
)
from app.services.command_service import (
    command_executed_service, command_auto_service,
    command_pending_get_service, command_door_service, command_relay_service,
)

router = APIRouter(prefix="/command", tags=["Command"])


@router.get("/pending", response_model=PendingCommandsResponse)
async def command_pending_get(_: User = Depends(verify_api_key),
                              db: AsyncSession = Depends(get_db)):
    return await command_pending_get_service(db)


@router.post("/{id}/executed", response_model=CommandStatusResponse)
async def command_executed(id: int,
                           _: User = Depends(verify_api_key),
                           db: AsyncSession = Depends(get_db)):
    return await command_executed_service(id, db)


@router.post("/door")
async def command_door(data: CommandDoorRequest,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    return await command_door_service(data, db)


@router.post("/auto", response_model=CommandStatusResponse)
async def command_auto(data: CommandAutoRequest,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    return await command_auto_service(data, db)


@router.post("/relay/heater", response_model=CommandStatusResponse)
async def command_heater(data: CommandRelayRequest,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    return await command_relay_service(CommandType.set_heater, data.state, db)


@router.post("/relay/vent", response_model=CommandStatusResponse)
async def command_vent(data: CommandRelayRequest,
                       user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    return await command_relay_service(CommandType.set_vent, data.state, db)


@router.post("/relay/light", response_model=CommandStatusResponse)
async def command_light(data: CommandRelayRequest,
                        user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    return await command_relay_service(CommandType.set_light, data.state, db)
