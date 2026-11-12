"""
cobd.py — "Determining COB Liability (COBD)", the client's decision procedure
(flowchart revised 07/07/25), as code.

Given the fields parsed from an 837D, `determine()` walks the flowchart node by
node and returns the path taken and where it ended. The same function is used
by the Dearborn backend (to draw the path on the claim page and brief the agent)
and by the AS/400 mock (edit 0230), so both always agree.

NOTE: this file is duplicated at  backend/cobd.py  and  as400/backend/cobd.py.
Keep the two identical.

What is implemented faithfully: the routing — every yes/no node 1-18 and which
terminal each branch lands on. What is NOT: the client's written text for
Rules 2, 3, 4, 5 and 6 was not provided. Rule 2 is applied as the standard
birthday rule and Rule 3 as the standard divorced-parents rule (court decree
first), both marked ASSUMED in the output. Rules 4, 5, 6 and Medicare liability
are not guessed: they end as UNDETERMINED and go to a technician.

hcsc_role in the result:
    SECONDARY      HCSC pays after the other plan   -> normal COB settlement
    PRIMARY        HCSC should have paid first      -> reprocess, recover other payer
    UNDETERMINED   the flow cannot settle it alone  -> technician with the rule named
"""
from __future__ import annotations

import re
from datetime import datetime

MEDICARE_RE = re.compile(r"medicare|medigap|\bsupp(lement)?\b", re.I)


def _dob(value):
    """Parse YYYY-MM-DD or YYYYMMDD into (month, day, year), else None."""
    if not value:
        return None
    d = re.sub(r"\D", "", str(value))
    if len(d) != 8:
        return None
    try:
        dt = datetime.strptime(d, "%Y%m%d")
    except ValueError:
        return None
    return (dt.month, dt.day, dt.year)


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower())


def determine(f: dict) -> dict:
    """Walk the COBD flowchart for one claim. `f` is the gold/parsed claim dict."""
    path: list[dict] = []

    def step(n, q, yes, ev):
        path.append({"n": n, "q": q, "a": "yes" if yes else "no", "ev": ev})
        return yes

    def end(node, label, role, rule=None, category="", to="", assumed=False, detail=""):
        return {
            "path": path,
            "terminal": {"node": node, "label": label, "rule": rule, "to": to,
                         "assumed": assumed, "detail": detail},
            "hcsc_role": role,
            "category": category,
            "needs_human": role != "SECONDARY",
        }

    primary = f.get("primary_payer") or "the other plan"

    # 1 ── eligibility
    eligible = bool(f.get("subscriber_id"))
    step(1, "Is patient eligible for DOS?", eligible,
         f"Member {f['subscriber_id']} on file." if eligible else "No subscriber ID on the claim.")
    if not eligible:
        return end(6, "Process and allow system denial", "UNDETERMINED",
                   category="Not eligible", to="Finalize or Pend")

    # 2 ── does HCSC coordinate with another plan
    coord = bool(f.get("cob_flag"))
    step(2, "Does BCBS coordinate with another plan?", coord,
         f"Other-payer loop present — {primary}." if coord else "No other-payer loop on the 837D.")
    if not coord:
        return end(7, "Process as Primary", "PRIMARY", category="No other coverage",
                   to="COB claim entry")

    # 3 ── is a determination needed
    needed = f.get("primary_paid_amount") is not None or bool(f.get("primary_eob_ref"))
    step(3, "Is determination needed?", needed,
         f"{primary} has already adjudicated — order of liability must be set." if needed
         else "Other plan has not adjudicated — nothing to determine yet.")
    if not needed:
        return end(8, "Process based on processor note", "UNDETERMINED",
                   category="No determination needed", to="COB claim entry")

    # 4 ── restricted group
    restricted = bool(f.get("restricted_group"))
    step(4, "Unable to process — restricted group?", restricted,
         "Group is flagged restricted." if restricted else "No restricted-group flag on the plan.")
    if restricted:
        return end(5, "Route to Security for processing", "UNDETERMINED",
                   category="Restricted group", to="End")

    # 9 ── Medicare / Medicare Supplement
    medicare = bool(MEDICARE_RE.search(primary))
    step(9, "Is one policy Medicare or Medicare Supp (Plan F, G or N)?", medicare,
         f"{primary} is Medicare / Medicare Supplement." if medicare
         else f"{primary} is commercial dental — not Medicare.")
    if medicare:
        liability_set = f.get("primary_paid_amount") is not None and bool(f.get("primary_eob_ref"))
        step(11, "Determine Medicare COB liability", True,
             "Medicare/Supplement paid first per the Medicare secondary-payer table.")
        step(10, "Was COB liability determined?", liability_set,
             "Paid amount and EOB reference both on file." if liability_set
             else "Missing payment evidence.")
        if liability_set:
            return end("COB", "COB claim entry", "SECONDARY", category="Medicare / Supplement",
                       to="COB claim entry",
                       detail="Medicare or the Supplement pays first; HCSC is secondary.")
        return end("DOC", "COB determine — no documentation", "UNDETERMINED",
                   category="Medicare / Supplement", to="COB determine no doc")

    # 12 ── different subscribers?
    ours, theirs = _norm(f.get("subscriber_name")), _norm(f.get("other_subscriber_name"))
    different = bool(ours and theirs and ours != theirs)
    step(12, "Different subscribers?", different,
         f"{f.get('subscriber_name')} (ours) vs {f.get('other_subscriber_name')} (other plan)."
         if different else "The same person holds both policies.")
    if not different:
        return end("4/5", "Rules 4 and 5", "UNDETERMINED", rule="Rules 4 & 5",
                   category="Same subscriber on both plans", to="Rules 4 and 5",
                   detail="The text of Rules 4 and 5 was not provided — technician to apply.")

    pat_rel = (f.get("patient_relationship") or "").upper()
    oth_rel = (f.get("other_relationship") or "").upper()

    # 13 ── is the patient OUR subscriber?
    ours_sub = pat_rel == "SELF"
    step(13, "Is patient our subscriber?", ours_sub,
         "Patient is the subscriber on our policy." if ours_sub
         else f"Patient is the subscriber's {pat_rel.lower() or 'dependent'}.")
    if ours_sub:
        return end(14, "Process as Primary (Rule 1)", "PRIMARY", rule="Rule 1",
                   category="Patient is our subscriber", to="COB claim entry",
                   detail=f"Rule 1: the plan covering the patient as subscriber pays first, "
                          f"so {primary}'s payment must be recovered.")

    # 15 ── is the patient the OTHER insurer's subscriber?
    other_sub = oth_rel == "SELF"
    step(15, "Is patient the OI subscriber?", other_sub,
         f"Patient is the subscriber on the {primary} policy." if other_sub
         else f"Patient is a {oth_rel.lower() or 'dependent'} on the {primary} policy.")
    if other_sub:
        return end(16, "Process as Secondary (Rule 1)", "SECONDARY", rule="Rule 1",
                   category="Patient is the other insurer's subscriber", to="COB claim entry",
                   detail=f"Rule 1: {primary} covers the patient as subscriber, so it pays first.")

    # 17 ── spouse on either policy?
    spouse = "SPOUSE" in (pat_rel, oth_rel)
    step(17, "Indication patient is spouse on either policy?", spouse,
         "Patient is a spouse on at least one policy." if spouse
         else "Patient is a child on both policies.")
    if spouse:
        return end("R6", "Rule 6", "UNDETERMINED", rule="Rule 6", category="Spouse on either policy",
                   to="Rule 6", detail="The text of Rule 6 was not provided — technician to apply.")

    # 18 ── parents separated / divorced?
    divorced = bool(f.get("parents_divorced"))
    step(18, "Indication parents are separated or divorced?", divorced,
         "Claim flags separated/divorced parents." if divorced else "Parents are not separated.")
    if divorced:
        order = (f.get("court_order") or "").upper()
        if order == "OTHER":
            return end("R3", "Rule 3", "SECONDARY", rule="Rule 3", category="Divorced — court order",
                       to="Rule 3", assumed=True,
                       detail="Court decree names the other plan as responsible → HCSC is secondary.")
        if order == "OUR":
            return end("R3", "Rule 3", "PRIMARY", rule="Rule 3", category="Divorced — court order",
                       to="Rule 3", assumed=True,
                       detail="Court decree names our plan as responsible → HCSC is primary.")
        return end("R3", "Rule 3", "UNDETERMINED", rule="Rule 3",
                   category="Divorced — no court order on file", to="Rule 3", assumed=True,
                   detail="No decree on file; custodial-parent evidence is needed.")

    # Rule 2 — default for a child covered through both parents
    mine, other = _dob(f.get("subscriber_dob")), _dob(f.get("other_subscriber_dob"))
    if mine and other:
        other_first = (other[0], other[1]) < (mine[0], mine[1])
        if (other[0], other[1]) == (mine[0], mine[1]):
            return end("R2", "Rule 2", "UNDETERMINED", rule="Rule 2",
                       category="Birthday rule — tie", to="Rule 2", assumed=True,
                       detail="Both parents share a birthday; longer-standing coverage decides.")
        who = primary if other_first else "our plan"
        return end("R2", "Rule 2", "SECONDARY" if other_first else "PRIMARY", rule="Rule 2",
                   category="Birthday rule", to="Rule 2", assumed=True,
                   detail=f"Birthday rule: the parent whose birthday falls earlier in the year "
                          f"({other[0]:02d}/{other[1]:02d} other vs {mine[0]:02d}/{mine[1]:02d} ours) → "
                          f"{who} is primary.")
    return end("R2", "Rule 2", "UNDETERMINED", rule="Rule 2", category="Birthday rule — dates missing",
               to="Rule 2", assumed=True, detail="Parent birth dates are missing from the claim.")


# Every place the flowchart can end, for the "all outcomes" legend in the UI.
OUTCOMES = [
    ("6",   "Not eligible for DOS",              "System denial"),
    ("7",   "No other coverage",                 "Process as primary"),
    ("8",   "No determination needed",           "Per processor note"),
    ("5",   "Restricted group",                  "Security"),
    ("COB", "Medicare / Supplement",             "Secondary"),
    ("4/5", "Same subscriber on both plans",     "Rules 4 & 5"),
    ("14",  "Patient is our subscriber",         "Primary (Rule 1)"),
    ("16",  "Patient is other insurer's sub.",   "Secondary (Rule 1)"),
    ("R6",  "Spouse on either policy",           "Rule 6"),
    ("R3",  "Separated / divorced parents",      "Rule 3"),
    ("R2",  "Child, married parents",            "Rule 2 birthday"),
]
