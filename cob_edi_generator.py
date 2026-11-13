"""
COB 837D EDI generator — produces Coordination of Benefits dental claims.

Every file written by this generator is a COB claim: the patient is covered by
two plans, so each 837D carries both an SBR*P (primary) and an SBR*S (secondary)
subscriber loop, plus the primary payer's AMT/OI payment detail.

Two flavours are produced, and the difference is the whole point of the demo:

  SIMPLE_COB
      Both plans settle the same way (both lump-sum, percentage coinsurance).
      The payer's AS/400 can reconcile this on its own: remaining = primary
      allowed minus primary paid, secondary owes its coinsurance share (fee
      schedule and annual max caps).
      No human needed.

  CROSS_PLAN_COB
      Primary paid a single lump sum. Secondary's plan only disburses on a
      fixed monthly schedule with a per-month cap. The two payment models do
      not reconcile arithmetically, so the AS/400 suspends the claim and it
      has to go to a human reviewer.

Usage:
    python cob_edi_generator.py                 # 12 files, default mix
    python cob_edi_generator.py --count 30
    python cob_edi_generator.py --out some/dir
    python cob_edi_generator.py --cross-plan-ratio 0.5
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).parent / "datasets" / "cob_edi"

# ── Reference data ────────────────────────────────────────────────────────────

PAYERS_PRIMARY = [
    ("CIGNA DENTAL PPO",        "62308"),
    ("DELTA DENTAL OF ILLINOIS", "05113"),
    ("AETNA DENTAL",            "60054"),
    ("METLIFE DENTAL",          "65978"),
    ("GUARDIAN DENTAL",         "64246"),
]

PAYER_SECONDARY = ("HCSC DENTAL", "00621")

# The destination plans. These mirror the rows seed_data.py puts in the Dearborn
# database, so a claim generated here resolves when the agent calls lookup_plan.
# seed_cob_claims.py creates the matching member, coverage and fee rows.
PLANS = [
    # plan_id,          state, coinsurance %, annual max
    ("PPO-SILVER-CA",   "CA",  50,            2000),
    ("PPO-GOLD-AZ",     "AZ",  50,            2500),
    ("PPO-GOLD-TX",     "TX",  50,            2000),
    ("PPO-SILVER-FL",   "FL",  50,            2000),
    ("PPO-BRONZE-IL",   "IL",  50,            1000),
    ("PPO-GOLD-NY",     "NY",  50,            2500),
]

PROVIDERS = [
    ("DEARBORN FAMILY DENTAL",   "1234567893"),
    ("LAKESHORE DENTAL GROUP",   "1548327690"),
    ("MIDWEST ORAL HEALTH PC",   "1902845571"),
    ("RIVERBEND DENTAL ASSOC",   "1760038824"),
]

SUBSCRIBERS = [
    ("MARGARET", "ELLISON"), ("DAVID", "OKONKWO"),   ("PRIYA", "RAGHUNATHAN"),
    ("THOMAS", "BRENNAN"),   ("SOFIA", "VARGAS"),    ("JAMES", "WHITFIELD"),
    ("AMARA", "NDIAYE"),     ("HENRY", "KOWALSKI"),  ("LINDA", "CHEN"),
    ("RAFAEL", "MENDOZA"),   ("GRACE", "ABIOLA"),    ("PETER", "SZABO"),
    ("NAOMI", "FUJIWARA"),   ("CARLOS", "RIVERA"),   ("ELEANOR", "HAYES"),
]

DEPENDENTS = [
    ("ETHAN", 9), ("MAYA", 12), ("LUCAS", 7), ("ZOE", 14),
    ("NOAH", 11), ("AVA", 8),   ("LIAM", 15), ("IRIS", 10),
]

# CDT code → (description, typical fee)
PROCEDURES = [
    ("D2740", "CROWN PORCELAIN CERAMIC",       1450.00),
    ("D2750", "CROWN PORCELAIN FUSED METAL",   1280.00),
    ("D6010", "IMPLANT BODY ENDOSTEAL",        2890.00),
    ("D6065", "IMPLANT SUPPORTED CROWN",       2150.00),
    ("D3330", "ENDODONTIC THERAPY MOLAR",       1180.00),
    ("D4341", "PERIO SCALING ROOT PLANE 4+",     320.00),
    ("D2950", "CORE BUILDUP INCL PINS",          285.00),
    ("D7210", "EXTRACTION ERUPTED TOOTH",        395.00),
]

TEETH = ["2", "3", "7", "12", "14", "18", "19", "30", "31"]

OTHER_FIRST = ["ANDREW", "MICHELLE", "DANIEL", "RACHEL", "SAMUEL", "HANNAH"]

MEDICARE_PAYERS = [
    ("MEDICARE PART B",                 "00882"),
    ("AARP MEDICARE SUPPLEMENT PLAN G", "60093"),
    ("MEDIGAP PLAN F",                  "73288"),
]

# ── COBD scenarios ────────────────────────────────────────────────────────────
# One per way the client's "Determining COB Liability" flowchart can end for a
# claim that already carries two plans. `role` is what the flow concludes for
# HCSC; it is checked against backend/cobd.py by the self-test at the bottom.
#   SECONDARY     HCSC pays after the other plan   (AS/400 may auto-pay it)
#   PRIMARY       HCSC should have paid first      (AS/400 suspends COB-05)
#   UNDETERMINED  flow cannot settle it alone      (AS/400 suspends COB-06)
SCENARIOS = {
    # name:                    (role,           flowchart ending)
    "SPOUSE_OI_SUBSCRIBER":    ("SECONDARY",    "Node 16 · patient is the other insurer's subscriber (Rule 1)"),
    "CHILD_BIRTHDAY_OTHER":    ("SECONDARY",    "Rule 2 · other parent's birthday is earlier"),
    "DIVORCED_COURT_OTHER":    ("SECONDARY",    "Rule 3 · decree names the other plan"),
    "MEDICARE_SUPPLEMENT":     ("SECONDARY",    "Nodes 9→11→10 · Medicare / Supplement pays first"),
    "SELF_OUR_SUBSCRIBER":     ("PRIMARY",      "Node 14 · patient is our subscriber (Rule 1)"),
    "CHILD_BIRTHDAY_OURS":     ("PRIMARY",      "Rule 2 · our subscriber's birthday is earlier"),
    "DIVORCED_COURT_OURS":     ("PRIMARY",      "Rule 3 · decree names our plan"),
    "DIVORCED_NO_ORDER":       ("UNDETERMINED", "Rule 3 · no court decree on file"),
    "SPOUSE_ON_POLICY":        ("UNDETERMINED", "Rule 6 · spouse on either policy"),
    "SAME_SUBSCRIBER":         ("UNDETERMINED", "Rules 4 & 5 · same subscriber on both plans"),
    "RESTRICTED_GROUP":        ("UNDETERMINED", "Node 5 · restricted group → Security"),
}
SCENARIO_NAMES = list(SCENARIOS)


# ── Case model ────────────────────────────────────────────────────────────────

@dataclass
class CobCase:
    case_type: str            # SIMPLE_COB | CROSS_PLAN_COB
    control_no: str
    subscriber_first: str
    subscriber_last: str
    subscriber_id: str
    dependent_first: str
    dependent_age: int
    plan_id: str
    plan_state: str
    plan_annual_max: int
    enrollment_date: datetime
    primary_payer: str
    primary_payer_id: str
    primary_member_id: str
    secondary_member_id: str
    provider_name: str
    provider_npi: str
    procedures: list[tuple[str, str, float, str]]   # code, desc, fee, tooth
    service_date: datetime
    primary_paid: float
    primary_allowed: float
    secondary_coinsurance: int        # percent
    primary_settlement: str           # LUMP_SUM | MONTHLY
    secondary_settlement: str         # LUMP_SUM | MONTHLY
    secondary_monthly_cap: float | None
    secondary_term_months: int | None
    primary_eob_ref: str
    # Supporting documents the practice sends with the claim (clinical notes,
    # history, EOB summary, COB questionnaire...). Held by Vyne, not in the EDI.
    details: dict | None = None

    # ── COBD liability scenario ──
    scenario: str = "CHILD_BIRTHDAY_OTHER"
    patient_rel: str = "CHILD"          # SELF | SPOUSE | CHILD — relation to OUR subscriber
    other_rel: str = "CHILD"            # patient's relation to the OTHER plan's subscriber
    other_sub_first: str = "ANDREW"
    other_sub_last: str = ""
    sub_dob: datetime | None = None
    other_dob: datetime | None = None
    parents_divorced: bool = False
    court_order: str | None = None      # OUR | OTHER | None
    restricted: bool = False

    @property
    def patient_first(self) -> str:
        return self.subscriber_first if self.patient_rel == "SELF" else self.dependent_first

    @property
    def role(self) -> str:
        return SCENARIOS[self.scenario][0]

    @property
    def billed(self) -> float:
        return round(sum(p[2] for p in self.procedures), 2)

    @property
    def filename(self) -> str:
        tag = {"CROSS_PLAN_COB": "XPLAN", "SIMPLE_COB": "SIMPLE"}.get(self.case_type, "LIAB")
        return f"COB_{tag}_{self.scenario}_{self.control_no}_{self.subscriber_last}.edi"


# ── Case construction ─────────────────────────────────────────────────────────

def _scenario_people(scenario: str, sub_first: str, sub_last: str, dep_first: str,
                     dep_age: int, rng: random.Random, service_date: datetime) -> dict:
    """Relationships, names and birth dates that make the flowchart land where intended."""
    other_first = rng.choice(OTHER_FIRST)
    spouse_first = rng.choice(["ROBERT", "CLAIRE", "MARCUS", "HELEN", "VICTOR", "DIANA"])
    sub_dob = service_date - timedelta(days=365 * rng.randint(36, 46) + rng.randint(0, 300))

    def other_dob_relative(other_earlier: bool) -> datetime:
        # The birthday rule compares month and day only, so shift within a
        # fixed leap-safe year and keep the birth year plausible.
        mine = (sub_dob.month, sub_dob.day)
        base = datetime(2001, sub_dob.month, min(sub_dob.day, 28))
        for _ in range(80):
            shift = timedelta(days=rng.randint(20, 150))
            cand = base - shift if other_earlier else base + shift
            if cand.year == 2001 and ((cand.month, cand.day) < mine) == other_earlier \
                    and (cand.month, cand.day) != mine:
                return datetime(sub_dob.year - rng.randint(0, 3), cand.month, cand.day)
        # Subscriber's birthday is too close to a year boundary for a 20+ day
        # shift; use the extreme date on the required side.
        return datetime(sub_dob.year - 1, 1, 1) if other_earlier else datetime(sub_dob.year - 1, 12, 31)

    p = dict(patient_rel="CHILD", other_rel="CHILD", other_first=other_first,
             other_last=sub_last, sub_dob=sub_dob, other_dob=other_dob_relative(True),
             patient_first=dep_first, divorced=False, court=None, restricted=False)

    if scenario == "SPOUSE_OI_SUBSCRIBER":
        p.update(patient_rel="SPOUSE", other_rel="SELF", patient_first=spouse_first,
                 other_first=spouse_first, dep_age=rng.randint(34, 44))
    elif scenario == "SELF_OUR_SUBSCRIBER":
        p.update(patient_rel="SELF", other_rel="SPOUSE", patient_first=sub_first,
                 other_first=spouse_first, dep_age=rng.randint(36, 46))
    elif scenario == "CHILD_BIRTHDAY_OTHER":
        p.update(other_dob=other_dob_relative(True))
    elif scenario == "CHILD_BIRTHDAY_OURS":
        p.update(other_dob=other_dob_relative(False))
    elif scenario == "DIVORCED_COURT_OTHER":
        p.update(divorced=True, court="OTHER")
    elif scenario == "DIVORCED_COURT_OURS":
        p.update(divorced=True, court="OUR")
    elif scenario == "DIVORCED_NO_ORDER":
        p.update(divorced=True, court=None)
    elif scenario == "SPOUSE_ON_POLICY":
        p.update(patient_rel="SPOUSE", other_rel="CHILD", patient_first=spouse_first,
                 dep_age=rng.randint(24, 28))
    elif scenario == "SAME_SUBSCRIBER":
        p.update(other_first=sub_first)
    elif scenario == "MEDICARE_SUPPLEMENT":
        p.update(patient_rel="SELF", other_rel="SELF", patient_first=sub_first,
                 other_first=sub_first, dep_age=rng.randint(66, 78))
    elif scenario == "RESTRICTED_GROUP":
        p.update(restricted=True)
    p.setdefault("dep_age", dep_age)
    return p


def _build_case(seq: int, cross_plan: bool, rng: random.Random,
                clears_in_term: bool = True,
                scenario: str = "CHILD_BIRTHDAY_OTHER") -> CobCase:
    sub_first, sub_last = rng.choice(SUBSCRIBERS)
    dep_first, dep_age  = rng.choice(DEPENDENTS)
    primary_payer, primary_payer_id = rng.choice(PAYERS_PRIMARY)
    if scenario == "MEDICARE_SUPPLEMENT":
        primary_payer, primary_payer_id = rng.choice(MEDICARE_PAYERS)
    # Only a claim the flow makes HCSC secondary can be a cross-plan settlement
    # problem; for every other scenario the liability question comes first.
    if SCENARIOS[scenario][0] != "SECONDARY":
        cross_plan = False
    prov_name, prov_npi = rng.choice(PROVIDERS)

    n_proc = rng.choice([1, 1, 2, 2, 3])
    chosen = rng.sample(PROCEDURES, n_proc)
    procedures = [
        (code, desc, round(fee * rng.uniform(0.92, 1.12), 2), rng.choice(TEETH))
        for code, desc, fee in chosen
    ]

    billed = round(sum(p[2] for p in procedures), 2)

    # Primary plan allows ~80% of billed and pays a coinsurance share of that.
    primary_allowed = round(billed * rng.uniform(0.74, 0.86), 2)
    primary_coins   = rng.choice([50, 60, 70, 80])
    primary_paid    = round(primary_allowed * primary_coins / 100, 2)

    service_date = datetime.now() - timedelta(days=rng.randint(12, 75))
    control_no   = f"{rng.randint(100000, 999999)}{seq:02d}"

    plan_id, state, plan_coins, annual_max = rng.choice(PLANS)
    # Subscriber IDs follow the HCSC-<state>-<8 digits> convention the Dearborn
    # member database uses, so lookup_member resolves.
    secondary_member_id = f"HCSC-{state}-{rng.randint(10000000, 99999999)}"
    # Enrolled well before the service date so no waiting-period edit fires.
    enrollment_date = service_date - timedelta(days=rng.randint(420, 1500))

    people = _scenario_people(scenario, sub_first, sub_last, dep_first, dep_age,
                              rng, service_date)
    dep_first, dep_age = people["patient_first"], people["dep_age"]

    if cross_plan:
        # The incompatible pair: primary settled in one lump sum, secondary's
        # plan only pays out on a capped monthly schedule.
        #
        # Whether that schedule can actually clear the debt is the interesting
        # variable. Pick the cap and term relative to the obligation so a known
        # share of claims genuinely cannot be settled inside the term — those
        # are the ones that still need a human. Without this every cross-plan
        # claim resolves and the escalation path is never exercised.
        remaining  = round(primary_allowed - primary_paid, 2)
        obligation = max(remaining * plan_coins / 100, 1.0)

        secondary_settlement  = "MONTHLY"
        secondary_term_months = rng.choice([6, 12, 18, 24])

        def _months(cap: float) -> int:
            return math.ceil(obligation / cap) if cap > 0 else 10 ** 6

        if clears_in_term:
            # Comfortably inside the term: the agent should resolve this.
            target = max(secondary_term_months - rng.randint(1, 4), 1)
            cap = max(5.0, round(obligation / target / 5) * 5)
            # Nudge upward until it genuinely clears — rounding can overshoot.
            while _months(cap) > secondary_term_months:
                cap += 5
        else:
            # Must NOT clear inside the term — a human has to override the
            # schedule. Aim past the term, then verify, because the rounding
            # and the minimum cap can otherwise rescue a small obligation.
            target = secondary_term_months + rng.randint(3, 12)
            cap = max(5.0, round(obligation / target / 5) * 5)
            while cap > 5 and _months(cap) <= secondary_term_months:
                cap -= 5
            if _months(cap) <= secondary_term_months:
                # Obligation too small for any sane cap to fall short — shorten
                # the term instead so the shortfall is real.
                secondary_term_months = max(1, _months(cap) - rng.randint(1, 3))

        secondary_monthly_cap = float(cap)
    else:
        secondary_settlement  = "LUMP_SUM"
        secondary_monthly_cap = None
        secondary_term_months = None

    case = CobCase(
        case_type            = ("LIABILITY_REVIEW" if SCENARIOS[scenario][0] != "SECONDARY"
                                else "CROSS_PLAN_COB" if cross_plan else "SIMPLE_COB"),
        control_no           = control_no,
        subscriber_first     = sub_first,
        subscriber_last      = sub_last,
        subscriber_id        = secondary_member_id,
        dependent_first      = dep_first,
        dependent_age        = dep_age,
        plan_id              = plan_id,
        plan_state           = state,
        plan_annual_max      = annual_max,
        enrollment_date      = enrollment_date,
        primary_payer        = primary_payer,
        primary_payer_id     = primary_payer_id,
        primary_member_id    = f"{primary_payer_id}{rng.randint(10000, 99999)}",
        secondary_member_id  = secondary_member_id,
        provider_name        = prov_name,
        provider_npi         = prov_npi,
        procedures           = procedures,
        service_date         = service_date,
        primary_paid         = primary_paid,
        primary_allowed      = primary_allowed,
        secondary_coinsurance= plan_coins,
        primary_settlement   = "LUMP_SUM",
        secondary_settlement = secondary_settlement,
        secondary_monthly_cap= secondary_monthly_cap,
        secondary_term_months= secondary_term_months,
        primary_eob_ref      = f"{primary_payer.split()[0]}-EOB-{service_date.year}-{rng.randint(10000, 99999)}",
        scenario             = scenario,
        patient_rel          = people["patient_rel"],
        other_rel            = people["other_rel"],
        other_sub_first      = people["other_first"],
        other_sub_last       = people["other_last"],
        sub_dob              = people["sub_dob"],
        other_dob            = people["other_dob"],
        parents_divorced     = people["divorced"],
        court_order          = people["court"],
        restricted           = people["restricted"],
    )
    case.details = _build_details(case, rng)
    return case


# ── Supporting documents (what Vyne holds beside the 837D) ────────────────────

NARRATIVES = {
    "D2740": "Tooth #{t}: large fracture with recurrent decay beneath an existing restoration; "
             "not enough sound structure left for a direct filling. Caries removed, full-coverage "
             "ceramic crown indicated.",
    "D2750": "Tooth #{t}: extensive coronal breakdown, cusp fracture. Porcelain-fused-to-metal "
             "crown indicated for strength under occlusal load.",
    "D6010": "Tooth #{t} missing after earlier extraction; adequate bone volume confirmed on "
             "imaging. Endosteal implant placed.",
    "D6065": "Implant at site #{t} integrated and stable; implant-supported crown delivered.",
    "D3330": "Tooth #{t}: lingering cold sensitivity, positive percussion, periapical radiolucency. "
             "Irreversible pulpitis; molar root canal therapy performed.",
    "D4341": "Generalised 5-6 mm pockets with bleeding on probing; radiographic bone loss. "
             "Scaling and root planing, four or more teeth in the quadrant.",
    "D2950": "Tooth #{t}: less than half of coronal structure remains. Core buildup placed to "
             "retain the planned crown.",
    "D7210": "Tooth #{t}: non-restorable (vertical root fracture). Erupted tooth extracted; "
             "socket preserved.",
}
XRAY_CODES = {"D2740", "D2750", "D3330", "D6010", "D6065", "D2950", "D7210"}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _build_details(c: CobCase, rng: random.Random) -> dict:
    sd = c.service_date
    first = c.procedures[0]
    tooth = first[3]

    narrative = " ".join(
        NARRATIVES.get(code, f"{desc.title()} performed on tooth #{t}.").format(t=t)
        for code, desc, _fee, t in c.procedures
    )

    # Earlier work in the same mouth — context a reviewer or a replacement-limit
    # edit would want.
    history = [
        {"date": _iso(sd - timedelta(days=rng.randint(170, 200))), "code": "D1110",
         "tooth": "", "note": "Adult prophylaxis; no concerns recorded"},
        {"date": _iso(sd - timedelta(days=rng.randint(170, 200))), "code": "D0274",
         "tooth": "", "note": "Four bitewing radiographs"},
    ]
    if first[0] in {"D2740", "D2750", "D2950", "D3330"}:
        history.append({
            "date": _iso(sd - timedelta(days=rng.randint(500, 1100))), "code": "D2391",
            "tooth": tooth, "note": f"Composite filling on #{tooth}; now failing",
        })

    primary_pct = round(c.primary_paid / c.primary_allowed * 100) if c.primary_allowed else 0
    eob = {
        "eob_ref": c.primary_eob_ref,
        "payer": c.primary_payer,
        "billed": c.billed,
        "allowed": c.primary_allowed,
        "paid": c.primary_paid,
        "patient_responsibility": round(c.primary_allowed - c.primary_paid, 2),
        "contractual_write_off": round(c.billed - c.primary_allowed, 2),
        "payment_date": _iso(sd + timedelta(days=14)),
        "payment_method": "EFT",
        "settlement": c.primary_settlement,
        "remark_codes": [
            "CO-45 Charge exceeds fee schedule (contractual write-off)",
            f"PR-2 Coinsurance — plan paid {primary_pct}% of allowed",
        ],
    }

    # Birthday rule: for a child on both parents' plans the parent whose birthday
    # falls earlier in the calendar year is primary. Computed, not asserted.
    sub_dob, other_dob = c.sub_dob, c.other_dob
    other_earlier = (other_dob.month, other_dob.day) < (sub_dob.month, sub_dob.day)
    other_first = c.other_sub_first

    questionnaire = {
        "other_coverage": True,
        "other_payer": c.primary_payer,
        "other_policyholder": f"{other_first} {c.other_sub_last or c.subscriber_last}",
        "other_member_id": c.primary_member_id,
        "other_policy_effective": _iso(c.enrollment_date - timedelta(days=rng.randint(30, 400))),
        "patient_relationship": {"SELF": "SELF", "SPOUSE": "SPOUSE", "CHILD": "CHILD"}[c.patient_rel],
        "patient_age": c.dependent_age,
        "our_subscriber": f"{c.subscriber_first} {c.subscriber_last}",
        "our_subscriber_dob": _iso(sub_dob),
        "other_policyholder_dob": _iso(other_dob),
        "birthday_rule_primary": "OTHER PLAN" if other_earlier else "OUR PLAN",
        "birthday_rule_consistent": other_earlier,   # claim lists the other plan as primary
        "court_order": c.court_order is not None,
        "parents_divorced": c.parents_divorced,
        "scenario": c.scenario,
        # The birthday rule only governs a child covered through both parents. For
        # every other scenario the viewer must not be shown it as the answer.
        "birthday_rule_applies": c.scenario.startswith("CHILD_BIRTHDAY"),
        "other_relationship": c.other_rel,
        "liability_note": SCENARIOS[c.scenario][1],
    }

    other_active_since = _iso(c.enrollment_date - timedelta(days=rng.randint(30, 400)))
    used = round(rng.uniform(0, 300), 2)
    eligibility = {
        "primary": {"payer": c.primary_payer, "active": True, "effective": other_active_since,
                    "annual_max": 1500, "remaining": round(1500 - rng.uniform(0, 400), 2)},
        "secondary": {"payer": PAYER_SECONDARY[0], "plan_id": c.plan_id, "active": True,
                      "effective": _iso(c.enrollment_date), "annual_max": c.plan_annual_max,
                      "remaining": round(c.plan_annual_max - used, 2)},
    }

    attachments = [
        {"type": "NARRATIVE", "name": "Clinical narrative", "date": _iso(sd), "pages": 1},
        {"type": "EOB", "name": f"Primary EOB {c.primary_eob_ref}", "date": _iso(sd + timedelta(days=14)), "pages": 2},
        {"type": "AOB", "name": "Signed assignment of benefits", "date": _iso(sd), "pages": 1},
    ]
    if any(p[0] in XRAY_CODES for p in c.procedures):
        attachments.append({"type": "XRAY", "name": f"Periapical radiograph, tooth #{tooth}",
                            "date": _iso(sd - timedelta(days=1)), "pages": 1})
    if any(p[0] in {"D6010", "D6065"} for p in c.procedures):
        attachments.append({"type": "XRAY", "name": "Panoramic radiograph",
                            "date": _iso(sd - timedelta(days=7)), "pages": 1})
    if any(p[0] == "D4341" for p in c.procedures):
        attachments.append({"type": "PERIO", "name": "Periodontal charting",
                            "date": _iso(sd), "pages": 2})

    prior_claims = [
        {"date": _iso(sd - timedelta(days=rng.randint(170, 200))), "payer": c.primary_payer,
         "code": "D1110", "billed": 125.00, "paid": 100.00},
        {"date": _iso(sd - timedelta(days=rng.randint(170, 200))), "payer": c.primary_payer,
         "code": "D0274", "billed": 70.00, "paid": 56.00},
        {"date": _iso(sd - timedelta(days=rng.randint(330, 370))), "payer": PAYER_SECONDARY[0],
         "code": "D1110", "billed": 125.00, "paid": 62.50},
    ]

    return {
        "clinical_narrative": narrative,
        "treatment_history": history,
        "prior_claims": prior_claims,
        "eob_summary": eob,
        "cob_questionnaire": questionnaire,
        "eligibility": eligibility,
        "attachments": attachments,
    }


# ── EDI serialisation ─────────────────────────────────────────────────────────

def _d8(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def render_edi(c: CobCase) -> str:
    """Render the case as an 837D transaction set with COB loops."""
    now = datetime.now()
    seg: list[str] = []
    add = seg.append

    ctrl = c.control_no

    # ── Interchange / functional group / transaction set ──────────────────────
    add(f"ISA*00*          *00*          *ZZ*DEARBORNDENTAL *ZZ*HCSCDENTAL     "
        f"*{now.strftime('%y%m%d')}*{now.strftime('%H%M')}*^*00501*{ctrl}*0*P*:")
    add(f"GS*HC*DEARBORNDENTAL*HCSCDENTAL*{_d8(now)}*{now.strftime('%H%M')}*{ctrl}*X*005010X224A2")
    add(f"ST*837*{ctrl[-4:]}*005010X224A2")
    add(f"BHT*0019*00*{ctrl}*{_d8(now)}*{now.strftime('%H%M')}*CH")

    # ── Submitter / receiver ──────────────────────────────────────────────────
    add("NM1*41*2*DEARBORN DENTAL CLEARING*****46*DBRN01")
    add("PER*IC*CLAIMS DESK*TE*3135551200")
    add("NM1*40*2*VYNE DENTAL GATEWAY*****46*VYNE01")

    # ── Billing provider ──────────────────────────────────────────────────────
    add("HL*1**20*1")
    add(f"NM1*85*2*{c.provider_name}*****XX*{c.provider_npi}")
    add("N3*4820 WOODWARD AVENUE SUITE 300")
    add("N4*DEARBORN*MI*48124")
    add(f"REF*EI*{c.provider_npi[:9]}")

    # ── Subscriber: SECONDARY plan (this is the claim's destination payer) ────
    add("HL*2*1*22*1")
    REL = {"SELF": "18", "SPOUSE": "01", "CHILD": "19"}
    self_pt = c.patient_rel == "SELF"
    add(f"SBR*S*{'18' if self_pt else ''}*{c.secondary_member_id}**{c.secondary_coinsurance}***CI")
    add(f"NM1*IL*1*{c.subscriber_last}*{c.subscriber_first}****MI*{c.secondary_member_id}")
    add("N3*1455 LAKEVIEW TERRACE")
    add("N4*CHICAGO*IL*60616")
    add(f"DMG*D8*{_d8(c.sub_dob)}*F")
    add(f"NM1*PR*2*{PAYER_SECONDARY[0]}*****PI*{PAYER_SECONDARY[1]}")

    # Secondary plan settlement rules — this is what the AS/400 reads
    add(f"REF*9F*SETTLE:{c.secondary_settlement}")
    if c.secondary_settlement == "MONTHLY":
        add(f"REF*G1*MONTHLYCAP:{c.secondary_monthly_cap:.2f}")
        add(f"REF*G3*TERMMONTHS:{c.secondary_term_months}")
    # Facts the COB liability flowchart (COBD) asks about
    if c.parents_divorced:
        add("REF*9F*PARENTS:DIVORCED")
        if c.court_order:
            add(f"REF*9F*COURTORDER:{c.court_order}")
    if c.restricted:
        add("REF*9F*GROUP:RESTRICTED")

    # ── Patient — a separate loop only when the patient is not the subscriber ─
    if not self_pt:
        add("HL*3*2*23*0")
        add(f"PAT*{REL[c.patient_rel]}")
        add(f"NM1*QC*1*{c.subscriber_last}*{c.dependent_first}")
        add("N3*1455 LAKEVIEW TERRACE")
        add("N4*CHICAGO*IL*60616")
        dob = c.service_date - timedelta(days=365 * c.dependent_age)
        add(f"DMG*D8*{_d8(dob)}*M")

    # ── Claim ─────────────────────────────────────────────────────────────────
    add(f"CLM*{ctrl}*{c.billed:.2f}***11:B:1*Y*A*Y*Y")
    add(f"DTP*472*D8*{_d8(c.service_date)}")
    add(f"REF*D9*{ctrl}")

    # ── Other payer loop (2320) — the PRIMARY plan and what it already paid ───
    add(f"SBR*P*{REL[c.other_rel]}*{c.primary_member_id}**{100 - c.secondary_coinsurance}***CI")
    add(f"AMT*D*{c.primary_paid:.2f}")            # payer paid amount
    add(f"AMT*B6*{c.primary_allowed:.2f}")        # allowed amount
    add("OI*Y*Y***Y")
    add(f"DTP*573*D8*{_d8(c.service_date + timedelta(days=rng_days()))}")
    add(f"NM1*IL*1*{c.other_sub_last or c.subscriber_last}*{c.other_sub_first}****MI*{c.primary_member_id}")
    add(f"DMG*D8*{_d8(c.other_dob)}*M")
    add(f"NM1*PR*2*{c.primary_payer}*****PI*{c.primary_payer_id}")
    add(f"REF*F8*{c.primary_eob_ref}")
    add(f"REF*9F*SETTLE:{c.primary_settlement}")

    # ── Service lines ─────────────────────────────────────────────────────────
    for i, (code, desc, fee, tooth) in enumerate(c.procedures, start=1):
        add(f"LX*{i}")
        add(f"SV3*AD:{code}*{fee:.2f}***{tooth}*1")
        add(f"DTP*472*D8*{_d8(c.service_date)}")
        add(f"REF*6R*{i}")
        # Primary payer's line-level adjudication
        line_paid = round(fee * (c.primary_paid / c.billed), 2) if c.billed else 0.0
        add(f"SVD*{c.primary_payer_id}*{line_paid:.2f}*AD:{code}**1")
        add(f"CAS*CO*45*{round(fee - line_paid, 2):.2f}")
        add(f"DTP*573*D8*{_d8(c.service_date + timedelta(days=14))}")

    add(f"SE*{len(seg) - 2}*{ctrl[-4:]}")
    add(f"GE*1*{ctrl}")
    add(f"IEA*1*{ctrl}")

    return "~\n".join(seg) + "~\n"


def rng_days() -> int:
    return random.randint(10, 30)


# ── Manifest ──────────────────────────────────────────────────────────────────

def _agent_outcome(c: CobCase, obligation: float) -> str:
    """
    What the Dearborn agent should conclude once the AS/400 refers the claim.

    A cross-plan claim is only genuinely unresolvable when the secondary's
    capped schedule cannot clear the obligation inside its term. Everything
    else is arithmetic the agent can finish on its own.
    """
    if c.case_type == "LIABILITY_REVIEW":
        what = ("HCSC is primary — reprocess and recover the other payer's payment"
                if c.role == "PRIMARY" else
                "flowchart cannot settle liability alone — technician applies the rule")
        return f"NEEDS_REVIEW — {SCENARIOS[c.scenario][1]}; {what}"
    if c.case_type != "CROSS_PLAN_COB":
        return "n/a — never reaches the agent"
    if not c.secondary_monthly_cap or not c.secondary_term_months:
        return "APPROVED — no schedule constraint"
    months = math.ceil(obligation / c.secondary_monthly_cap)
    if months <= c.secondary_term_months:
        return f"APPROVED — clears in {months} of {c.secondary_term_months} months"
    return (f"NEEDS_REVIEW — needs {months} months, term is only "
            f"{c.secondary_term_months}; override required")


def write_manifest(cases: list[CobCase], out_dir: Path) -> None:
    import json

    rows = []
    for c in cases:
        remaining = round(c.primary_allowed - c.primary_paid, 2)
        secondary_owed = round(remaining * c.secondary_coinsurance / 100, 2)
        rows.append({
            "filename":              c.filename,
            "case_type":             c.case_type,
            "control_no":            c.control_no,
            "scenario":              c.scenario,
            "cobd_role":             c.role,
            "cobd_ending":           SCENARIOS[c.scenario][1],
            "patient":               f"{c.patient_first} {c.subscriber_last}",
            "patient_dob":           (c.sub_dob if c.patient_rel == "SELF"
                                      else c.service_date - timedelta(days=365 * c.dependent_age)
                                      ).strftime("%Y-%m-%d"),
            "subscriber":            f"{c.subscriber_first} {c.subscriber_last}",
            "subscriber_id":         c.subscriber_id,
            "plan_id":               c.plan_id,
            "plan_state":            c.plan_state,
            "plan_annual_max":       c.plan_annual_max,
            "enrollment_date":       c.enrollment_date.strftime("%Y-%m-%d"),
            "service_date":          c.service_date.strftime("%Y-%m-%d"),
            "provider_name":         c.provider_name,
            "provider_npi":          c.provider_npi,
            "procedures":            [
                {"cdt_code": code, "description": desc, "fee": fee, "tooth": tooth}
                for code, desc, fee, tooth in c.procedures
            ],
            "primary_payer":         c.primary_payer,
            "primary_payer_id":      c.primary_payer_id,
            "primary_allowed":       c.primary_allowed,
            "primary_eob_ref":       c.primary_eob_ref,
            "billed":                c.billed,
            "primary_paid":          c.primary_paid,
            "remaining":             remaining,
            "secondary_coinsurance": c.secondary_coinsurance,
            "secondary_owed":        secondary_owed,
            "primary_settlement":    c.primary_settlement,
            "secondary_settlement":  c.secondary_settlement,
            "secondary_monthly_cap": c.secondary_monthly_cap,
            "secondary_term_months": c.secondary_term_months,
            "as400_outcome": (
                "SUSPEND COB-03 → refer to agent" if c.case_type == "CROSS_PLAN_COB"
                else ("SUSPEND COB-05 (HCSC is primary) → refer to agent" if c.role == "PRIMARY"
                      else "SUSPEND COB-06 (liability undetermined) → refer to agent")
                if c.case_type == "LIABILITY_REVIEW"
                else "AUTO-ADJUDICATE → paid"
            ),
            "agent_outcome": _agent_outcome(c, secondary_owed),
            "months_needed": (
                math.ceil(secondary_owed / c.secondary_monthly_cap)
                if c.secondary_monthly_cap else None
            ),
            "details":               c.details,
        })

    (out_dir / "manifest.json").write_text(json.dumps(rows, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

def generate(count: int, cross_plan_ratio: float, out_dir: Path, seed: int | None,
             override_ratio: float = 0.4) -> list[CobCase]:
    rng = random.Random(seed)
    if seed is not None:
        random.seed(seed)

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.edi"):
        try:
            stale.unlink()
        except OSError as exc:
            # A locked or read-only leftover shouldn't stop generation — the new
            # files are written over the top anyway.
            print(f"  note: could not remove {stale.name} ({exc.strerror})")

    # Every COBD flowchart ending gets a claim before any repeats, so a batch of
    # 11 or more shows the client every branch.
    scenarios: list[str] = []
    while len(scenarios) < count:
        batch = SCENARIO_NAMES[:]
        rng.shuffle(batch)
        scenarios.extend(batch)
    scenarios = scenarios[:count]

    # Cross-plan settlement only applies where the flow makes HCSC secondary.
    secondary_idx = [i for i, s in enumerate(scenarios) if SCENARIOS[s][0] == "SECONDARY"]
    n_cross = min(len(secondary_idx), max(1, round(len(secondary_idx) * cross_plan_ratio))) \
        if secondary_idx else 0
    cross_idx = set(rng.sample(secondary_idx, n_cross)) if n_cross else set()

    # Of the cross-plan claims, a share get a schedule that genuinely cannot
    # clear the obligation inside its term. Those are the ones the agent should
    # escalate — the rest it should resolve on its own.
    n_override = max(1, round(n_cross * override_ratio)) if n_cross else 0
    override_flags = [False] * n_override + [True] * (n_cross - n_override)
    rng.shuffle(override_flags)

    cases = []
    for i, scen in enumerate(scenarios):
        is_cross = i in cross_idx
        clears = override_flags.pop() if (is_cross and override_flags) else True
        cases.append(_build_case(i + 1, is_cross, rng, clears_in_term=clears, scenario=scen))

    for c in cases:
        (out_dir / c.filename).write_text(render_edi(c), encoding="utf-8")

    write_manifest(cases, out_dir)
    return cases


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate COB 837D dental EDI claims")
    ap.add_argument("--count", type=int, default=12, help="number of claims to generate")
    ap.add_argument("--cross-plan-ratio", type=float, default=0.4,
                    help="fraction that are CROSS_PLAN_COB (suspended by the AS/400)")
    ap.add_argument("--override-ratio", type=float, default=0.4,
                    help="of the cross-plan claims, the fraction whose monthly "
                         "schedule cannot clear the obligation inside its term — "
                         "these are the ones the agent must escalate to a human")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--seed", type=int, default=None, help="seed for reproducible output")
    args = ap.parse_args()

    cases = generate(args.count, args.cross_plan_ratio, args.out, args.seed,
                     override_ratio=args.override_ratio)

    n_cross  = sum(1 for c in cases if c.case_type == "CROSS_PLAN_COB")
    n_liab   = sum(1 for c in cases if c.case_type == "LIABILITY_REVIEW")
    n_simple = len(cases) - n_cross - n_liab

    print("=" * 78)
    print("  COB 837D EDI GENERATOR")
    print("=" * 78)
    print(f"  Output dir        : {args.out}")
    print(f"  Claims written    : {len(cases)}")
    print(f"    SIMPLE_COB      : {n_simple}  (AS/400 auto-adjudicates)")
    print(f"    CROSS_PLAN_COB  : {n_cross}  (AS/400 suspends COB-03)")
    print(f"    LIABILITY_REVIEW: {n_liab}  (AS/400 suspends COB-05/06 — COBD flowchart)")
    print("=" * 78)
    for c in cases:
        marker = "!!" if c.case_type != "SIMPLE_COB" else "  "
        print(f" {marker} {c.scenario:<24} {c.role:<13} {SCENARIOS[c.scenario][1]}")
    print("=" * 68)
    print("  Manifest written to manifest.json (expected outcome per claim)")


if __name__ == "__main__":
    main()
