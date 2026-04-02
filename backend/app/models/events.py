from pydantic import BaseModel


class WSEvent(BaseModel):
    event_type: str  # transcript_update, tool_call, call_status, coverage_decision, next_action, notification
    call_id: str
    timestamp: str
    payload: dict
