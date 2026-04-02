"""Tool handlers called by the Gemini Live voice agent mid-conversation."""
import asyncio
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

# Will be set to the async coverage evaluator at import time
_coverage_evaluator = None

_customers: dict | None = None


def _load_customers() -> dict:
    global _customers
    if _customers is None:
        with open(os.path.join(DATA_DIR, "mock_customers.json")) as f:
            _customers = json.load(f)
    return _customers


def validate_account(policy_number: str) -> dict:
    """Validate a customer's insurance account by policy number."""
    customers = _load_customers()
    customer = customers.get(policy_number.upper().strip())
    if customer is None:
        return {"valid": False, "error": f"No account found for policy number {policy_number}"}
    if customer["status"] == "expired":
        return {"valid": False, "error": f"Policy {policy_number} has expired on {customer['expiry']}", "customer_name": customer["name"]}
    if customer["status"] == "suspended":
        return {"valid": False, "error": f"Policy {policy_number} is currently suspended", "customer_name": customer["name"]}
    return {
        "valid": True,
        "customer_name": customer["name"],
        "vehicle": customer["vehicle"],
        "plan": customer["plan"],
        "expiry": customer["expiry"],
    }


def classify_incident(description: str) -> dict:
    """Classify the type of roadside incident from a description."""
    desc_lower = description.lower()
    classifications = [
        (["flat tire", "flat tyre", "tire blowout", "puncture", "blown tire"], "flat_tire"),
        (["engine", "won't start", "wont start", "overheating", "smoke", "stalled", "died"], "engine_failure"),
        (["accident", "crash", "collision", "hit", "fender bender"], "accident"),
        (["locked out", "lockout", "keys locked", "key inside", "lost key", "locked my keys"], "lockout"),
        (["fuel", "gas", "ran out", "empty tank", "no gas", "no fuel"], "fuel_empty"),
        (["battery", "dead battery", "jump start", "won't turn over"], "battery_dead"),
    ]
    for keywords, incident_type in classifications:
        if any(kw in desc_lower for kw in keywords):
            return {"incident_type": incident_type, "confidence": 0.9}
    return {"incident_type": "other", "confidence": 0.5}


def get_policy_metadata(policy_number: str) -> dict:
    """Get summary of coverage details for a validated policy."""
    customers = _load_customers()
    customer = customers.get(policy_number.upper().strip())
    if customer is None:
        return {"error": f"Policy {policy_number} not found"}

    plan = customer["plan"]
    coverage_details = {
        "basic": {
            "towing_miles": 25,
            "tow_claims_per_year": 2,
            "lockout_covered": False,
            "fuel_delivery_gallons": 2,
            "fuel_cost_covered": False,
            "battery_service": False,
            "accident_assistance": False,
            "vehicle_recovery": False,
        },
        "standard": {
            "towing_miles": 50,
            "tow_claims_per_year": 4,
            "lockout_covered": True,
            "lockout_claims_per_year": 2,
            "fuel_delivery_gallons": 3,
            "fuel_cost_covered": True,
            "battery_service": True,
            "accident_assistance": True,
            "vehicle_recovery": False,
        },
        "premium": {
            "towing_miles": "unlimited",
            "tow_claims_per_year": "unlimited",
            "lockout_covered": True,
            "lockout_claims_per_year": "unlimited",
            "fuel_delivery_gallons": 5,
            "fuel_cost_covered": True,
            "battery_service": True,
            "accident_assistance": True,
            "vehicle_recovery": True,
            "trip_interruption": True,
        },
    }

    return {
        "policy_number": policy_number,
        "plan": plan,
        "customer_name": customer["name"],
        "vehicle": customer["vehicle"],
        "status": customer["status"],
        "expiry": customer["expiry"],
        "coverage": coverage_details.get(plan, {}),
    }


async def check_coverage(policy_number: str, incident_type: str, situation_summary: str) -> dict:
    """Check coverage using the RAG coverage evaluator."""
    from app.services.coverage_agent import evaluate_coverage
    from app.models.call import IncidentData

    customers = _load_customers()
    customer = customers.get(policy_number.upper().strip())
    if customer is None:
        return {"status": "not_covered", "explanation": f"Policy {policy_number} not found in our system."}

    plan = customer["plan"]
    incident = IncidentData(
        customer_name=customer["name"],
        policy_number=policy_number,
        vehicle=customer["vehicle"],
        incident_type=incident_type,
        situation_summary=situation_summary,
    )

    try:
        decision = await evaluate_coverage(incident, plan)
        return {
            "status": decision.status,
            "confidence": decision.confidence,
            "cited_clauses": decision.cited_clauses,
            "explanation": decision.explanation,
            "requires_human_review": decision.requires_human_review,
            "plan": plan,
            "customer_name": customer["name"],
        }
    except Exception as e:
        print(f"Coverage check error: {e}")
        return {
            "status": "uncertain",
            "explanation": f"Unable to complete coverage check: {e}. Please transfer to a human agent.",
            "requires_human_review": True,
        }


def dispatch_service(policy_number: str, incident_type: str, coverage_status: str) -> dict:
    """Dispatch roadside assistance service after coverage is confirmed and customer agrees."""
    if coverage_status != "covered":
        return {
            "dispatched": False,
            "error": f"Cannot dispatch: coverage status is '{coverage_status}'. Service can only be dispatched when coverage is 'covered'.",
        }

    from app.services.next_action import determine_next_action
    action = determine_next_action(incident_type)

    return {
        "dispatched": True,
        "service_type": action.service_type,
        "provider": action.assigned_garage.name,
        "provider_address": action.assigned_garage.address,
        "provider_phone": action.assigned_garage.phone,
        "distance_miles": action.assigned_garage.distance_miles,
        "eta_minutes": action.assigned_garage.eta_minutes,
        "estimated_arrival": action.estimated_arrival,
        "message": f"{action.service_type} dispatched. {action.assigned_garage.name} is {action.assigned_garage.distance_miles} miles away, ETA {action.assigned_garage.eta_minutes} minutes.",
    }


def transfer_to_human_agent(reason: str) -> dict:
    """Initiate transfer to a human agent."""
    return {
        "transfer_initiated": True,
        "reason": reason,
        "message": "Transferring to a human agent now. Please hold.",
    }


# Registry for dispatching tool calls by name
TOOL_REGISTRY = {
    "validate_account": validate_account,
    "classify_incident": classify_incident,
    "get_policy_metadata": get_policy_metadata,
    "check_coverage": check_coverage,
    "dispatch_service": dispatch_service,
    "transfer_to_human_agent": transfer_to_human_agent,
}


async def dispatch_tool(tool_name: str, args: dict) -> dict:
    """Dispatch a tool call by name and return the result."""
    handler = TOOL_REGISTRY.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    result = handler(**args)
    # Support both sync and async handlers
    if asyncio.iscoroutine(result):
        return await result
    return result
