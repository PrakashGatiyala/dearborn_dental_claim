"""
seed_cob_claims.py — makes the generated COB claims resolvable by the AI agent.

The agent in backend/agent.py adjudicates by calling six database lookups:
lookup_member, lookup_plan, lookup_coverage_rules, lookup_fee_schedule,
lookup_ortho_history and lookup_primary_eob. If the subscriber on a claim isn't
in the member table, every one of those returns "not found" and the agent has
nothing to reason over — it falls through to NEEDS_REVIEW with no analysis.

This script reads datasets/cob_edi/manifest.json and upserts, for every
generated claim:

    Member          the subscriber, on a real plan, enrolled before the service
                    date, with secondary_insurance naming the primary payer
    PlanMember      the dependent child who received treatment
    CoverageRule    one rule per CDT prefix used, on that member's plan
    FeeSchedule     a contracted fee for each CDT code used
    EobRecord       the primary payer's EOB — what it paid and how it settled

Run it after generating the dataset and before sending claims:

    python cob_edi_generator.py --count 12
    python seed_cob_claims.py
    python vyne_sender.py --all

Requires DATABASE_URL, or it uses whatever backend/database.py defaults to.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))

from database import (                                      # noqa: E402
    CoverageRule, EobRecord, FeeSchedule, Member, Plan, PlanMember,
    SessionLocal, create_tables,
)

MANIFEST = ROOT / "datasets" / "cob_edi" / "manifest.json"

# Plans the generator draws from, matching seed_data.py.
PLAN_ROWS = [
    ("PPO-SILVER-CA", "HCSC PPO Silver CA", "Silver", 2000, 150, 0.5, 0),
    ("PPO-GOLD-AZ",   "HCSC PPO Gold AZ",   "Gold",   2500, 150, 0.5, 3000),
    ("PPO-GOLD-TX",   "HCSC PPO Gold TX",   "Gold",   2000, 150, 0.5, 3000),
    ("PPO-SILVER-FL", "HCSC PPO Silver FL", "Silver", 2000, 150, 0.5, 0),
    ("PPO-BRONZE-IL", "HCSC PPO Bronze IL", "Bronze", 1000, 200, 0.5, 0),
    ("PPO-GOLD-NY",   "HCSC PPO Gold NY",   "Gold",   2500, 150, 0.5, 0),
]

CATEGORY = {
    "D27": "Crown", "D29": "Restorative", "D33": "Endodontics",
    "D43": "Periodontics", "D60": "Implant", "D72": "Extraction",
    "D01": "Preventive", "D02": "Diagnostic",
}


def _category(cdt: str) -> str:
    return CATEGORY.get(cdt[:3], "General Dentistry")


def seed() -> None:
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} not found.")
        print("       Generate the dataset first:  python cob_edi_generator.py --count 12")
        sys.exit(1)

    rows = json.loads(MANIFEST.read_text())
    create_tables()
    db = SessionLocal()

    counts = dict(plans=0, members=0, plan_members=0, rules=0, fees=0, eobs=0, removed=0)

    # ── Plans ────────────────────────────────────────────────────────────────
    for pid, name, tier, annual, ded, coins, ortho in PLAN_ROWS:
        if not db.query(Plan).filter_by(plan_id=pid).first():
            db.add(Plan(plan_id=pid, plan_name=name, plan_type="PPO", tier=tier,
                        annual_max=annual, deductible=ded, coinsurance_pct=coins,
                        lifetime_ortho_max=ortho))
            counts["plans"] += 1
    db.commit()

    # ── Clean slate: drop COB demo rows left by earlier runs ─────────────────
    # Every regenerate mints new subscriber IDs, so without this the member and
    # EOB tables fill with rows no claim refers to. Only rows this script created
    # (group id GRP-COB-*) are touched; the base seed_data.py rows are left alone.
    keep = {r["subscriber_id"] for r in rows}
    stale = [m.subscriber_id for m in db.query(Member).filter(Member.group_id.like("GRP-COB-%"))
             if m.subscriber_id not in keep]
    if stale:
        db.query(EobRecord).filter(EobRecord.subscriber_id.in_(stale)).delete(synchronize_session=False)
        db.query(PlanMember).filter(PlanMember.subscriber_id.in_(stale)).delete(synchronize_session=False)
        db.query(Member).filter(Member.subscriber_id.in_(stale)).delete(synchronize_session=False)
        db.commit()
    counts["removed"] = len(stale)

    for r in rows:
        sid     = r["subscriber_id"]
        plan_id = r["plan_id"]
        d       = r.get("details") or {}
        q       = d.get("cob_questionnaire") or {}

        # ── Member — the subscriber who carries the secondary plan ───────────
        if not db.query(Member).filter_by(subscriber_id=sid).first():
            db.add(Member(
                subscriber_id       = sid,
                name                = r["subscriber"].title(),
                dob                 = q.get("our_subscriber_dob", "1986-05-14"),
                plan_id             = plan_id,
                enrollment_date     = r["enrollment_date"],
                group_id            = f"GRP-COB-{r['plan_state']}",
                # This is what tells the agent the claim has COB.
                secondary_insurance = r["primary_payer"].title(),
                is_active           = True,
            ))
            counts["members"] += 1

        # ── Plan member — the dependent child actually treated ───────────────
        member_id = f"{sid}-02"
        if not db.query(PlanMember).filter_by(member_id=member_id).first():
            db.add(PlanMember(
                plan_id      = plan_id,
                subscriber_id= sid,
                member_name  = r["patient"].title(),
                relationship = (q.get("patient_relationship") or "dependent").lower(),
                dob          = r["patient_dob"],
                member_id    = member_id,
            ))
            counts["plan_members"] += 1

        # ── Coverage rules and fee schedule for every code on the claim ──────
        for proc in r["procedures"]:
            code, fee = proc["cdt_code"], float(proc["fee"])
            prefix = code[:4]

            if not db.query(CoverageRule).filter_by(plan_id=plan_id, cdt_prefix=prefix).first():
                db.add(CoverageRule(
                    plan_id                   = plan_id,
                    cdt_prefix                = prefix,
                    procedure_category        = _category(code),
                    coverage_pct              = r["secondary_coinsurance"] / 100,
                    # No predetermination or x-ray gate: these claims are meant to
                    # turn on the COB settlement question, not get denied on an
                    # unrelated edit.
                    requires_predetermination = False,
                    requires_xray             = False,
                    waiting_period_months     = 0,
                    min_amount_for_predet     = 0,
                ))
                counts["rules"] += 1

            if not db.query(FeeSchedule).filter_by(plan_id=plan_id, cdt_code=code).first():
                db.add(FeeSchedule(
                    plan_id         = plan_id,
                    cdt_code        = code,
                    procedure_name  = proc["description"].title(),
                    ucr_fee         = fee,
                    ppo_allowed_fee = round(fee * 0.85, 2),
                ))
                counts["fees"] += 1

        # ── Primary payer's EOB — the heart of the COB calculation ───────────
        eob = db.query(EobRecord).filter_by(subscriber_id=sid).first()
        eob_fields = dict(
            eob_number              = r["primary_eob_ref"],
            primary_plan_id         = r["primary_payer_id"],
            primary_plan_name       = r["primary_payer"].title(),
            cdt_codes               = json.dumps([p["cdt_code"] for p in r["procedures"]]),
            billed_amount           = r["billed"],
            primary_paid_amount     = r["primary_paid"],
            primary_allowed_amount  = r["primary_allowed"],
            payment_type            = "lump_sum",
            monthly_amount          = None,
            months_paid             = None,
            claim_date              = r["service_date"],
            remaining_balance       = r["remaining"],
        )
        if not eob:
            db.add(EobRecord(subscriber_id=sid, **eob_fields))
            counts["eobs"] += 1
        else:
            for k, v in eob_fields.items():
                setattr(eob, k, v)

    db.commit()
    db.close()

    print("=" * 62)
    print("  COB CLAIM SEED")
    print("=" * 62)
    print(f"  Claims in manifest     : {len(rows)}")
    print(f"  Stale COB rows removed : {counts['removed']}")
    print(f"  Plans inserted         : {counts['plans']}")
    print(f"  Members inserted       : {counts['members']}")
    print(f"  Plan members inserted  : {counts['plan_members']}")
    print(f"  Coverage rules inserted: {counts['rules']}")
    print(f"  Fee schedules inserted : {counts['fees']}")
    print(f"  EOB records inserted   : {counts['eobs']}")
    print("=" * 62)
    print("  Every generated claim now resolves against the member database.")


if __name__ == "__main__":
    seed()
