"""RAG-based coverage decision agent using Gemini."""
import json
import os

from google import genai
from google.genai import types

from app.models.call import IncidentData, CoverageDecision
from app.rag.retriever import PolicyRetriever

# Map plan names to PDF filename fragments for filtering
PLAN_TO_SOURCE = {
    "basic": "basic",
    "standard": "standard",
    "premium": "premium",
}


async def evaluate_coverage(incident: IncidentData, plan: str) -> CoverageDecision:
    """Evaluate whether an incident is covered under the customer's policy using RAG."""
    retriever = PolicyRetriever()

    # Build retrieval query from incident details
    query = f"{incident.incident_type} {incident.situation_summary or ''} {incident.vehicle or ''}"
    plan_filter = PLAN_TO_SOURCE.get(plan)
    chunks = retriever.retrieve(query, top_k=5, plan_filter=plan_filter)

    # Build context from retrieved chunks
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"[Source: {chunk.source}, Page {chunk.page}]\n{chunk.text}"
        )
    policy_context = "\n\n---\n\n".join(context_parts)

    # Build the prompt for Gemini
    prompt = f"""You are an insurance coverage analyst. Based on the policy document excerpts below, determine whether the following incident is covered.

POLICY EXCERPTS:
{policy_context}

INCIDENT DETAILS:
- Customer: {incident.customer_name}
- Vehicle: {incident.vehicle}
- Location: {incident.location}
- Incident Type: {incident.incident_type}
- Situation: {incident.situation_summary}
- Plan Tier: {plan}

Analyze the policy excerpts and provide a coverage decision. Respond with a JSON object with these exact fields:
- "status": one of "covered", "not_covered", or "uncertain"
- "confidence": a float between 0.0 and 1.0 indicating your confidence
- "cited_clauses": a list of specific section references from the policy (e.g., "Section 3 - Flat Tire Assistance")
- "explanation": a clear explanation of why the incident is or is not covered, referencing specific policy terms

Respond ONLY with the JSON object, no other text."""

    client = genai.Client(
        http_options={"api_version": "v1beta"},
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    # Parse the response
    try:
        result = json.loads(response.text)
        decision = CoverageDecision(
            status=result.get("status", "uncertain"),
            confidence=float(result.get("confidence", 0.5)),
            cited_clauses=result.get("cited_clauses", []),
            explanation=result.get("explanation", "Unable to determine coverage."),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        decision = CoverageDecision(
            status="uncertain",
            confidence=0.3,
            cited_clauses=[],
            explanation=f"Error parsing coverage analysis. Raw response: {response.text[:200]}",
        )

    decision.requires_human_review = decision.confidence < 0.7
    return decision
