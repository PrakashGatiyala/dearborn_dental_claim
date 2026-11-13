"""Shared COB arithmetic (allowed-based remainder, optional fee + annual max caps)."""
from __future__ import annotations


def _coinsurance_frac(pct: float | int) -> float:
    p = float(pct)
    return p / 100.0 if p > 1 else p


def compute_cob_settlement(
    *,
    billed: float,
    primary_allowed: float | None,
    primary_paid: float,
    coinsurance_pct: float | int,
    hcsc_ppo_allowed_total: float | None = None,
    annual_max: float | int | None = None,
) -> dict:
    if primary_allowed is None:
        return {"ok": False, "error": "primary_allowed_missing"}

    billed = float(billed)
    primary_allowed = float(primary_allowed)
    primary_paid = float(primary_paid)
    remaining_cob = round(primary_allowed - primary_paid, 2)
    if remaining_cob < 0:
        remaining_cob = 0.0

    frac = _coinsurance_frac(coinsurance_pct)
    secondary = round(remaining_cob * frac, 2)

    if hcsc_ppo_allowed_total is not None and hcsc_ppo_allowed_total > 0:
        fee_cap = round(float(hcsc_ppo_allowed_total) * frac, 2)
        secondary = min(secondary, fee_cap)

    if annual_max is not None:
        secondary = min(secondary, float(annual_max))

    member = round(remaining_cob - secondary, 2)
    total_pay = round(primary_paid + secondary, 2)
    overpayment_ok = total_pay <= billed + 0.01

    return {
        "ok": True,
        "remaining_cob": remaining_cob,
        "secondary_owes": secondary,
        "member_liability": member,
        "overpayment_ok": overpayment_ok,
        "total_plan_pay": total_pay,
        "contractual_writeoff": round(billed - primary_allowed, 2),
    }
