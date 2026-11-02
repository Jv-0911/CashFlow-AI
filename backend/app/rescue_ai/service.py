"""Public rescue orchestration: deterministic facts, optional bounded AI selection.

Integration usage (inside an async API route):
    result = await analyze_rescue(request)  # deterministic, no credentials needed
    result = await analyze_rescue(request, provider=configured_provider)

Provider setup belongs to the caller. This module never reads environment files,
constructs a provider automatically, executes payments, or changes source records.
"""

import asyncio

from .fallback import analyze_fallback
from .provider import (
    ProviderDecision, RescueProvider, build_provider_context, validate_decision,
)
from .schemas import RescueAnalysisRequest, RescueResponse


# Only code-owned sentences may supplement the computed financial explanation.
# Each key must be both a valid provider code and supported by the trusted context.
_EXPLANATIONS = {
    "reserve_breach": "The supplied forecast indicates a potential reserve breach.",
    "reserve_boundary": "The projected balance reaches the reserve with no margin above it.",
    "above_reserve": "The assessed balances remain above the reserve under the supplied assumptions.",
    "insufficient_evidence": "There is insufficient current forecast evidence to assess risk.",
    "overdue_invoices": "Overdue unpaid invoices provide possible follow-up actions.",
    "upcoming_expenses": "Upcoming projected expenses can be reviewed with the scenario engine.",
    "collection_uncertain": "Customer collection and its timing remain uncertain; proposed recovery is not received cash.",
}


async def analyze_rescue(
    request: RescueAnalysisRequest,
    provider: RescueProvider | None = None,
    *,
    timeout_seconds: float = 15.0,
) -> RescueResponse:
    """Return analysis without allowing an AI provider to change financial facts.

    Invalid input raises ValidationError before any provider call. An absent
    provider, or a forecast with no current/future evidence, returns the baseline.
    A configured provider may reorder all existing actions and select supported
    explanation codes. Monetary facts, evidence, uncertainty and approval flags
    come only from the baseline, including when the provider mutates its copy.

    Provider errors, invalid output and timeouts return deterministic analysis
    with a generic notice. Cancellation of the caller is deliberately propagated.
    The deadline bounds cooperative async providers; blocking synchronous code
    inside a custom provider cannot be forcibly interrupted by asyncio.
    """
    if (isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 < timeout_seconds <= 60):
        raise ValueError("timeout_seconds must be a finite number greater than 0 and at most 60")

    # The fallback revalidates the request and creates independently owned output.
    # Keep validation outside the provider boundary so bad inputs are never hidden.
    baseline = analyze_fallback(request)
    if provider is None or baseline.risk_level == "unknown":
        return baseline

    context = build_provider_context(baseline)
    try:
        async with asyncio.timeout(timeout_seconds):
            raw = await provider.analyze(baseline.model_copy(deep=True))
        # Rebuild a provider model from values, rather than trusting a possibly
        # mutated/model_construct-created Pydantic instance or custom adapter.
        value = raw.model_dump(mode="json") if isinstance(raw, ProviderDecision) else raw
        decision = validate_decision(value, context)
        return _apply_decision(baseline, decision)
    except asyncio.CancelledError:
        raise
    except Exception:
        # The provider/assembly boundary must not expose upstream exception text.
        # Construct the fallback after leaving this handler so a later error
        # cannot chain a private provider exception into its traceback.
        pass

    result = baseline.model_dump(mode="json")
    result["assumptions"].append(
        "AI analysis was unavailable or rejected; deterministic analysis is shown."
    )
    return RescueResponse.model_validate(result)


def _apply_decision(
    baseline: RescueResponse, decision: ProviderDecision,
) -> RescueResponse:
    """Apply AI choices without replacing any trusted financial facts.

    Independently enforce a full permutation and supported explanation points,
    even if provider validation is weakened during a later integration change.
    Any assembly error is handled by analyze_rescue's fallback boundary.
    """
    actions_by_id = {action.action_id: action for action in baseline.recommended_actions}
    if (len(decision.action_ids) != len(actions_by_id)
            or set(decision.action_ids) != set(actions_by_id)):
        raise ValueError("AI selections must reorder every existing action exactly once")
    allowed_points = build_provider_context(baseline)["allowed_explanation_points"]
    if (not decision.explanation_points
            or len(decision.explanation_points) != len(set(decision.explanation_points))
            or not set(decision.explanation_points).issubset(allowed_points)
            or allowed_points[0] not in decision.explanation_points):
        raise ValueError("AI explanation points must be supported by the baseline")

    result = baseline.model_dump(mode="json")
    result["recommended_actions"] = []
    for priority, action_id in enumerate(decision.action_ids, start=1):
        action = actions_by_id[action_id].model_dump(mode="json")
        action["priority"] = priority
        result["recommended_actions"].append(action)
    result["summary"] = baseline.summary + " " + " ".join(
        _EXPLANATIONS[point] for point in decision.explanation_points
    )
    result["source"] = "ai"
    result["assumptions"].append(
        "AI selected explanation points and action order; calculations and financial facts remain deterministic."
    )
    return RescueResponse.model_validate(result)
