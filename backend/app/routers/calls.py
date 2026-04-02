"""REST endpoints for call management."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.call_store import call_store
from app.services.event_bus import event_bus
from app.models.events import WSEvent

router = APIRouter(prefix="/calls", tags=["calls"])


class OverrideRequest(BaseModel):
    action: str  # approve, deny, escalate
    notes: str = ""


@router.get("")
async def list_calls():
    return [c.model_dump() for c in call_store.list_calls()]


@router.get("/{call_id}")
async def get_call(call_id: str):
    call = call_store.get_call(call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return call.model_dump()


@router.post("/{call_id}/override")
async def override_call(call_id: str, req: OverrideRequest):
    call = call_store.get_call(call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    call.human_override = f"{req.action}: {req.notes}"
    await event_bus.publish(WSEvent(
        event_type="human_override",
        call_id=call_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        payload={"action": req.action, "notes": req.notes},
    ))
    return {"status": "ok", "override": call.human_override}
