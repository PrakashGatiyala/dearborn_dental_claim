"""Read HCSC plan / fee data from public schema (same DB as claims)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from database import FeeSchedule, Member, Plan, SessionLocal


def _fee_total(db: Session, plan_id: str, cdt_codes: list[str]) -> float | None:
    total = 0.0
    found = 0
    for code in cdt_codes:
        row = db.query(FeeSchedule).filter_by(plan_id=plan_id, cdt_code=code).first()
        if row:
            total += float(row.ppo_allowed_fee)
            found += 1
    return round(total, 2) if found else None


def payer_context_for_gold(gold: dict) -> dict | None:
    sid = gold.get("subscriber_id")
    if not sid:
        return None
    codes = gold.get("cdt_codes") or []
    if isinstance(codes, str):
        try:
            codes = json.loads(codes)
        except json.JSONDecodeError:
            codes = []
    db = SessionLocal()
    try:
        member = db.query(Member).filter_by(subscriber_id=sid).first()
        if not member:
            return None
        plan = db.query(Plan).filter_by(plan_id=member.plan_id).first()
        return {
            "annual_max": plan.annual_max if plan else None,
            "deductible": plan.deductible if plan else None,
            "plan_coinsurance_pct": plan.coinsurance_pct if plan else None,
            "ppo_allowed_total": _fee_total(db, member.plan_id, codes),
        }
    finally:
        db.close()
