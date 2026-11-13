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
    """
    remaining_cob = primary_allowed - primary_paid
    secondary_owes = remaining_cob * coinsurance, capped by fee schedule and annual max
    member_liability = remaining_cob - secondary_owes (patient share of COB remainder)
    """
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


def compute_hcsc_primary_adjudication(
    *,
    billed: float,
    ppo_allowed_total: float | None,
    deductible: float | int | None,
    deductible_met: bool,
    plan_coinsurance_pct: float | None,
    annual_max: float | int | None,
) -> dict:
    """
    HCSC as true primary: PPO allowed, deductible (if not met), then plan pays its
    coinsurance share of the remainder, capped by annual max.
    """
    billed = float(billed)
    if ppo_allowed_total is None or ppo_allowed_total <= 0:
        return {"ok": False, "error": "ppo_allowed_missing"}
    allowed = round(float(ppo_allowed_total), 2)
    ded = float(deductible or 0)
    plan_frac = float(plan_coinsurance_pct if plan_coinsurance_pct is not None else 0.5)
    if plan_frac > 1:
        plan_frac = plan_frac / 100.0

    ded_applied = 0.0 if deductible_met else min(ded, allowed)
    eligible = round(allowed - ded_applied, 2)
    plan_pay = round(eligible * plan_frac, 2)
    if annual_max is not None:
        plan_pay = min(plan_pay, float(annual_max))

    member_coins = round(eligible * (1.0 - plan_frac), 2)
    above_contract = round(max(0.0, billed - allowed), 2)
    member = round(ded_applied + member_coins + above_contract, 2)

    return {
        "ok": True,
        "ppo_allowed_total": allowed,
        "deductible_applied": round(ded_applied, 2),
        "hcsc_plan_pay": plan_pay,
        "member_liability": member,
        "contractual_writeoff": above_contract,
    }
