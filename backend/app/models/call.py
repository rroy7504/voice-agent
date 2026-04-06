from datetime import datetime
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class IncidentData(BaseModel):
    customer_name: Optional[str] = None
    policy_number: Optional[str] = None
    vehicle: Optional[str] = None
    location: Optional[str] = None
    incident_type: Optional[str] = None  # flat_tire, engine_failure, accident, lockout, fuel_empty, other
    situation_summary: Optional[str] = None


class CoverageDecision(BaseModel):
    status: str  # covered, not_covered, uncertain
    confidence: float = Field(ge=0.0, le=1.0)
    cited_clauses: list[str] = []
    explanation: str = ""
    requires_human_review: bool = False


class GarageInfo(BaseModel):
    name: str
    address: str
    distance_miles: float
    eta_minutes: int
    phone: str


class NextAction(BaseModel):
    recommended_action: str  # dispatch_tow_truck, dispatch_repair_vehicle, dispatch_locksmith, dispatch_fuel_delivery
    service_type: str
    assigned_garage: GarageInfo
    estimated_arrival: str


class CustomerNotification(BaseModel):
    reference_number: str
    message_text: str
    coverage_summary: str
    assistance_type: str
    eta: Optional[str] = None


class TranscriptEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    role: str  # customer, agent
    text: str
    timestamp: str


class ToolCallEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    tool: str
    input: dict
    output: dict
    timestamp: str


class CallState(BaseModel):
    call_id: str
    status: str = "active"  # active, processing, completed
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    incident: IncidentData = Field(default_factory=IncidentData)
    transcript: list[TranscriptEntry] = []
    tool_calls: list[ToolCallEntry] = []
    coverage: Optional[CoverageDecision] = None
    action: Optional[NextAction] = None
    notification: Optional[CustomerNotification] = None
    human_override: Optional[str] = None
