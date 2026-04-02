from pydantic import BaseModel


class CustomerInfo(BaseModel):
    name: str
    policy_number: str
    vehicle: str
    plan: str  # basic, standard, premium
    status: str  # active, expired, suspended
    expiry: str


class PolicyChunk(BaseModel):
    text: str
    source: str  # filename
    page: int
    chunk_id: str
    score: float = 0.0
