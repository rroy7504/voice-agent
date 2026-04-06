from uuid import uuid4
from pydantic import BaseModel, Field


class WSEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    event_type: str  # transcript_update, tool_call, call_status, coverage_decision, next_action, notification
    call_id: str
    timestamp: str
    payload: dict
