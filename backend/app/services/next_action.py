"""Determine next best action and assign nearest garage."""
import random
from datetime import datetime, timedelta

from app.models.call import NextAction, GarageInfo

INCIDENT_TO_SERVICE = {
    "flat_tire": ("dispatch_repair_vehicle", "Mobile Tire Repair"),
    "engine_failure": ("dispatch_tow_truck", "Tow Truck"),
    "accident": ("dispatch_tow_truck", "Tow Truck"),
    "lockout": ("dispatch_locksmith", "Locksmith Service"),
    "fuel_empty": ("dispatch_fuel_delivery", "Fuel Delivery"),
    "battery_dead": ("dispatch_repair_vehicle", "Mobile Battery Service"),
    "other": ("dispatch_tow_truck", "Tow Truck"),
}

MOCK_GARAGES = [
    GarageInfo(name="AutoCare Express", address="142 Main St, Springfield", distance_miles=2.3, eta_minutes=15, phone="555-0101"),
    GarageInfo(name="Quick Fix Auto", address="88 Oak Avenue, Springfield", distance_miles=4.1, eta_minutes=22, phone="555-0202"),
    GarageInfo(name="Highway Rescue Services", address="501 Interstate Blvd", distance_miles=5.8, eta_minutes=28, phone="555-0303"),
    GarageInfo(name="24/7 Roadside Pros", address="77 Elm Street, Shelbyville", distance_miles=8.2, eta_minutes=35, phone="555-0404"),
    GarageInfo(name="Metro Towing & Recovery", address="200 Industrial Park Dr", distance_miles=11.5, eta_minutes=42, phone="555-0505"),
]


def determine_next_action(incident_type: str) -> NextAction:
    """Pick the right service and nearest available garage."""
    action_key, service_type = INCIDENT_TO_SERVICE.get(incident_type, INCIDENT_TO_SERVICE["other"])

    # Pick the nearest garage (simulate some randomness in availability)
    available = random.sample(MOCK_GARAGES, k=min(3, len(MOCK_GARAGES)))
    garage = min(available, key=lambda g: g.distance_miles)

    eta = datetime.utcnow() + timedelta(minutes=garage.eta_minutes)

    return NextAction(
        recommended_action=action_key,
        service_type=service_type,
        assigned_garage=garage,
        estimated_arrival=eta.isoformat() + "Z",
    )
