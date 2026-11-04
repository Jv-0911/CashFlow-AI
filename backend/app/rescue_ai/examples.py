"""Reproducible, local-only rescue demonstrations using fictional USD records.

Run from the repository root:
    python -B -m backend.app.rescue_ai.examples --scenario all --pretty

Nothing is written, no credentials are read, and no network call is made.
The ai_selection case uses a simulated provider, not a real AI model.
"""

import argparse
import asyncio
import json
from collections.abc import Sequence

from .provider import ProviderDecision, ProviderError, build_provider_context
from .schemas import RescueAnalysisRequest, RescueResponse
from .service import analyze_rescue


DEMO_SCENARIOS = (
    "shortage", "safe", "reserve_boundary", "insufficient_evidence",
    "stale", "paid_invoice", "provider_failure", "ai_selection",
)


class _SimulatedSelectionProvider:
    """Exercise the accepted AI-selection path without connecting to a model."""

    async def analyze(self, baseline: RescueResponse) -> ProviderDecision:
        context = build_provider_context(baseline)
        return ProviderDecision(
            action_ids=[action.action_id for action in reversed(baseline.recommended_actions)],
            explanation_points=context["allowed_explanation_points"],
        )


class _SimulatedUnavailableProvider:
    """Exercise service fallback without connecting to a provider."""

    async def analyze(self, baseline: RescueResponse) -> ProviderDecision:
        raise ProviderError("PROVIDER_UNAVAILABLE")


def build_demo_request(scenario: str = "shortage") -> RescueAnalysisRequest:
    """Build a fresh fictional snapshot; fixed dates avoid clock-dependent demos.

    The basic case starts with 120000 cents, expects 20000 cents, and owes
    80000 cents in wages. The supplied forecast closes at 60000 cents against
    a 100000-cent reserve. A separate 80000-cent overdue invoice is uncertain.
    This fixture arithmetic constructs demo data, not a replacement forecast engine.
    """
    if scenario not in DEMO_SCENARIOS:
        raise ValueError(f"Unknown demo scenario: {scenario}")
    opening = {"safe": 240000, "reserve_boundary": 160000}.get(scenario, 120000)
    closing = opening + 20000 - 80000
    data = {
        "as_of_date": "2026-10-26",
        "forecast_id": "forecast_demo_001",
        "forecast": {
            "currency": "USD", "safety_reserve_cents": 100000,
            "first_reserve_breach_date": "2026-10-27" if closing < 100000 else None,
            "is_demo": True,
            "disclaimer": "Fictional demo records; no bank, PayPal or live AI connection.",
            "days": [{
                "date": "2026-10-27", "opening_balance_cents": opening,
                "receipts_cents": 20000, "expenses_cents": 80000,
                "closing_balance_cents": closing,
            }],
        },
        "invoices": [{
            "invoice_id": "INV-DEMO-104", "currency": "USD",
            "outstanding_amount_cents": 80000,
            "due_date": "2026-10-20", "status": "unpaid",
        }],
        "transactions": [{
            "transaction_id": "WAGES-DEMO-001", "currency": "USD",
            "amount_cents": 80000, "date": "2026-10-27",
            "direction": "expense", "status": "projected", "discretionary": False,
        }],
    }
    if scenario == "insufficient_evidence":
        data["forecast"].update(days=[], first_reserve_breach_date=None)
    elif scenario == "stale":
        data["as_of_date"] = "2026-10-28"
    elif scenario == "paid_invoice":
        # Status alone never credits cash. The caller owns the opening balance.
        data["invoices"][0].update(status="paid", outstanding_amount_cents=0)
    return RescueAnalysisRequest.model_validate(data)


async def run_demo(scenario: str = "shortage") -> dict:
    """Return demo request plus output, with explicit simulation metadata."""
    request = build_demo_request(scenario)
    provider = None
    mode = "disabled"
    if scenario == "provider_failure":
        provider = _SimulatedUnavailableProvider()
        mode = "simulated_failure"
    elif scenario == "ai_selection":
        provider = _SimulatedSelectionProvider()
        mode = "simulated_selection"
    response = await analyze_rescue(request, provider)
    result = response.model_dump(mode="json")
    if mode == "simulated_selection":
        result["assumptions"].append(
            "DEMO: the provider selection was simulated locally; no AI model was called."
        )
    return {
        "scenario": scenario, "is_demo": True, "provider_mode": mode,
        "request": request.model_dump(mode="json"), "response": result,
    }


async def _run_selected(scenario: str) -> dict | list[dict]:
    if scenario == "all":
        return [await run_demo(name) for name in DEMO_SCENARIOS]
    return await run_demo(scenario)


def main(argv: Sequence[str] | None = None) -> None:
    """Print JSON to stdout only; an unknown scenario exits with usage error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("all", *DEMO_SCENARIOS), default="all")
    parser.add_argument("--pretty", action="store_true", help="Indent the output JSON")
    args = parser.parse_args(argv)
    result = asyncio.run(_run_selected(args.scenario))
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=True))


if __name__ == "__main__":
    main()
