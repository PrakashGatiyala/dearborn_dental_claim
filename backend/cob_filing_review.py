"""COB-05: filed order vs COBD liability (side-by-side math + auditor narrative)."""
from __future__ import annotations

from cob_settlement import compute_cob_settlement, compute_hcsc_primary_adjudication
from payer_data import payer_context_for_gold


def compute_filing_vs_cobd(
    gold: dict | None,
    cobd: dict | None,
    suspend_code: str | None = None,
) -> dict | None:
    if not gold or not gold.get("cob_flag") or not cobd:
        return None
    if cobd.get("hcsc_role") != "PRIMARY":
        return None

    try:
        billed = float(gold["billed_amount"])
        other_paid = float(gold["primary_paid_amount"])
    except (TypeError, ValueError, KeyError):
        return None

    filed_primary = gold.get("primary_payer") or "the other plan"
    other_allowed = gold.get("primary_allowed_amount")
    if other_allowed is not None:
        try:
            other_allowed = float(other_allowed)
        except (TypeError, ValueError):
            other_allowed = None
    coins = gold.get("secondary_coinsurance")
    if coins is None:
        return None

    ctx = payer_context_for_gold(gold) or {}
    as_filed = compute_cob_settlement(
        billed=billed,
        primary_allowed=other_allowed,
        primary_paid=other_paid,
        coinsurance_pct=coins,
        hcsc_ppo_allowed_total=ctx.get("ppo_allowed_total"),
        annual_max=ctx.get("annual_max"),
    )

    corrected = compute_hcsc_primary_adjudication(
        billed=billed,
        ppo_allowed_total=ctx.get("ppo_allowed_total"),
        deductible=ctx.get("deductible"),
        deductible_met=bool(gold.get("deductible_met")),
        plan_coinsurance_pct=ctx.get("plan_coinsurance_pct"),
        annual_max=ctx.get("annual_max"),
    )

    recovery = round(other_paid, 2)

    payload = {
        "suspend_code": "COB-05",
        "filed_primary": filed_primary,
        "billed_amount": billed,
        "cobd_role": cobd.get("hcsc_role"),
        "cobd_terminal": cobd.get("terminal"),
        "recovery_amount": recovery,
        "as_filed": as_filed if as_filed.get("ok") else {"ok": False, "error": as_filed.get("error")},
        "as_corrected": corrected if corrected.get("ok") else {"ok": False, "error": corrected.get("error")},
    }
    if not corrected.get("ok"):
        return None
    return payload


def display_metrics_for_claim(
    gold: dict | None,
    cobd: dict | None,
    suspend_code: str | None,
) -> dict | None:
    """Tiles use as-filed secondary COB; COB-05 narrative carries corrected amounts."""
    review = compute_filing_vs_cobd(gold, cobd, suspend_code)
    filed = review.get("as_filed") if review else None
    if filed and filed.get("ok"):
        return {
            "remaining_balance": filed.get("remaining_cob"),
            "secondary_owes": filed.get("secondary_owes"),
            "member_liability": filed.get("member_liability"),
            "provisional": True,
        }
    from cob_display_metrics import compute_cob_display_metrics

    return compute_cob_display_metrics(gold, suspend_code)
