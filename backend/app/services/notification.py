"""Generate structured customer notification that summarizes the actual call."""
import uuid

from app.models.call import CallState, CustomerNotification


def generate_notification(call: CallState) -> CustomerNotification:
    """Generate a notification summarizing the decisions made during the call."""
    ref = f"REF-{uuid.uuid4().hex[:8].upper()}"
    name = call.incident.customer_name or "valued customer" if call.incident else "valued customer"

    # Build a summary from what actually happened
    lines = [f"Hi {name},", "", f"Here's a summary of your call ({ref}):", ""]

    # Account info
    if call.incident and call.incident.policy_number:
        lines.append(f"Policy: {call.incident.policy_number}")
        if call.incident.vehicle:
            lines.append(f"Vehicle: {call.incident.vehicle}")
        lines.append("")

    # What happened
    if call.incident and call.incident.situation_summary:
        lines.append(f"Issue reported: {call.incident.situation_summary}")
        if call.incident.incident_type:
            lines.append(f"Classified as: {call.incident.incident_type.replace('_', ' ').title()}")
        lines.append("")

    # Coverage decision
    if call.coverage:
        if call.coverage.status == "covered":
            lines.append("Coverage: APPROVED")
            if call.coverage.explanation:
                lines.append(f"Details: {call.coverage.explanation}")
        elif call.coverage.status == "not_covered":
            lines.append("Coverage: NOT APPROVED")
            if call.coverage.explanation:
                lines.append(f"Reason: {call.coverage.explanation}")
        else:
            lines.append("Coverage: UNDER REVIEW")
            if call.coverage.explanation:
                lines.append(f"Note: {call.coverage.explanation}")
        lines.append("")

    # Action taken
    if call.action:
        lines.append("Next steps:")
        lines.append(f"  - {call.action.recommended_action}")
        if call.action.assigned_garage:
            g = call.action.assigned_garage
            lines.append(f"  - Provider: {g.name} ({g.distance_miles} mi away)")
            lines.append(f"  - ETA: {g.eta_minutes} minutes")
            lines.append(f"  - Provider phone: {g.phone}")
        lines.append("")

    # If no coverage/action was determined
    if not call.coverage and not call.action:
        # Check if it was a transfer
        was_transferred = any(
            tc.tool == "transfer_to_human_agent" for tc in call.tool_calls
        )
        if was_transferred:
            transfer_reason = next(
                (tc.input.get("reason", "") for tc in call.tool_calls if tc.tool == "transfer_to_human_agent"),
                ""
            )
            lines.append(f"Your call was transferred to a human agent.")
            if transfer_reason:
                lines.append(f"Reason: {transfer_reason}")
            lines.append("A specialist will follow up with you shortly.")
        else:
            lines.append("Your request is being processed. We'll follow up shortly.")
        lines.append("")

    lines.append("For questions, call 1-800-555-HELP.")

    message = "\n".join(lines)

    # Determine summary fields
    coverage_summary = ""
    if call.coverage:
        coverage_summary = {
            "covered": "Approved",
            "not_covered": "Not approved",
            "uncertain": "Under review",
        }.get(call.coverage.status, "Pending")

    assistance_type = "N/A"
    eta = None
    if call.action:
        assistance_type = call.action.service_type
        eta = f"{call.action.assigned_garage.eta_minutes} minutes" if call.action.assigned_garage else None

    return CustomerNotification(
        reference_number=ref,
        message_text=message,
        coverage_summary=coverage_summary or "Pending",
        assistance_type=assistance_type,
        eta=eta,
    )
