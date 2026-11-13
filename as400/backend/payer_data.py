"""
HCSC plan / member / fee data for the AS/400 adjudicator.

Same Postgres database as Dearborn (`public` schema), populated by
`seed_data.py` and `seed_cob_claims.py`. The AS/400 service only reads
these tables — it does not own them.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Boolean, Column, Float, Integer, MetaData, String
from sqlalchemy.orm import Session, declarative_base

from database import SessionLocal

_public = MetaData(schema="public")
PublicBase = declarative_base(metadata=_public)


class Plan(PublicBase):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    plan_id = Column(String)
    annual_max = Column(Integer)
    coinsurance_pct = Column(Float)


class Member(PublicBase):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True)
    subscriber_id = Column(String)
    plan_id = Column(String)
    is_active = Column(Boolean)


class FeeSchedule(PublicBase):
    __tablename__ = "fee_schedules"
    id = Column(Integer, primary_key=True)
    plan_id = Column(String)
    cdt_code = Column(String)
    ppo_allowed_fee = Column(Float)


def verify_reference_data() -> dict[str, Any]:
    """Startup check: can we read shared payer tables?"""
    db = SessionLocal()
    try:
        members = db.query(Member).count()
        plans = db.query(Plan).count()
        fees = db.query(FeeSchedule).count()
        return {
            "ok": members > 0 and plans > 0,
            "members": members,
            "plans": plans,
            "fee_schedules": fees,
            "hint": None if members else "Run seed_cob_claims.py (Dearborn repo root).",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "hint": "Check DATABASE_URL and migrations."}
    finally:
        db.close()


def lookup_member_plan(db: Session, subscriber_id: str) -> dict | None:
    row = db.query(Member).filter_by(subscriber_id=subscriber_id).first()
    if not row:
        return None
    plan = db.query(Plan).filter_by(plan_id=row.plan_id).first()
    return {
        "subscriber_id": row.subscriber_id,
        "plan_id": row.plan_id,
        "is_active": row.is_active,
        "annual_max": plan.annual_max if plan else None,
        "plan_coinsurance_pct": plan.coinsurance_pct if plan else None,
    }


def sum_ppo_allowed(db: Session, plan_id: str, cdt_codes: list[str]) -> float | None:
    if not plan_id or not cdt_codes:
        return None
    total = 0.0
    found = 0
    for code in cdt_codes:
        row = db.query(FeeSchedule).filter_by(plan_id=plan_id, cdt_code=code).first()
        if row:
            total += float(row.ppo_allowed_fee)
            found += 1
    return round(total, 2) if found else None


def cob_reference_context(subscriber_id: str, cdt_codes: list[str] | str) -> dict | None:
    """Snapshot for adjudication: member, plan limits, contracted allowed total."""
    if isinstance(cdt_codes, str):
        try:
            cdt_codes = json.loads(cdt_codes)
        except (json.JSONDecodeError, TypeError):
            cdt_codes = [c.strip() for c in cdt_codes.split(",") if c.strip()]
    db = SessionLocal()
    try:
        mp = lookup_member_plan(db, subscriber_id)
        if not mp:
            return None
        ppo_total = sum_ppo_allowed(db, mp["plan_id"], cdt_codes)
        return {**mp, "ppo_allowed_total": ppo_total}
    finally:
        db.close()
