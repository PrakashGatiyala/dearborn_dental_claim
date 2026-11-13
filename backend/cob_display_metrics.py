"""Display-only COB figures when approved_amount is null (suspended COB claims)."""
from __future__ import annotations

from cob_settlement import compute_cob_settlement
from payer_data import payer_context_for_gold


def compute_cob_display_metrics(gold: dict | None, suspend_code: str | None = None) -> dict | None:
    if not gold or not gold.get("cob_flag"):
        return None
    try:
        billed = float(gold["billed_amount"])
        primary_paid = float(gold["primary_paid_amount"])
    except (TypeError, ValueError, KeyError):
        return None
    allowed = gold.get("primary_allowed_amount")
    if allowed is not None:
        try:
            allowed = float(allowed)
        except (TypeError, ValueError):
            allowed = None
    coins = gold.get("secondary_coinsurance")
    if coins is None:
        return None

    ctx = payer_context_for_gold(gold) or {}
    settle = compute_cob_settlement(
        billed=billed,
        primary_allowed=allowed,
        primary_paid=primary_paid,
        coinsurance_pct=coins,
        hcsc_ppo_allowed_total=ctx.get("ppo_allowed_total"),
        annual_max=ctx.get("annual_max"),
    )
    if not settle.get("ok"):
        return None
    return {
        "remaining_balance": settle["remaining_cob"],
        "secondary_owes": settle["secondary_owes"],
        "member_liability": settle["member_liability"],
        "provisional": suspend_code in ("COB-03", "COB-05", "COB-06"),
    }
