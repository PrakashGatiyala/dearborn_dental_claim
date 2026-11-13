"""
COB adjudication engine for the HCSC AS/400 mock.

This is deliberately written the way a legacy batch adjudicator behaves: a fixed
sequence of numbered edits, each either passing or raising a suspend code. There
is no inference and no judgement — if an edit cannot be satisfied by arithmetic
on the data in the claim, the claim suspends and a human has to work it.

The edit that matters for this demo is EDIT 0640 — COB SETTLEMENT RECONCILIATION.

    Primary plan settled LUMP_SUM and secondary plan settles LUMP_SUM
        → one subtraction and one percentage. The box can do it.

    Primary plan settled LUMP_SUM but secondary plan settles MONTHLY with a
    per-month cap
        → the secondary obligation is a single coordinated amount, but the
          disbursement rules only permit N payments of at most $CAP. Where the
          obligation exceeds what the schedule can disburse inside the term,
          the two plans' payment models do not reconcile. The legacy system has
          no instruction for that case, so it suspends on COB-03.
"""

from __future__ import annotations

import re

from cobd import determine
from cob_settlement import compute_cob_settlement

# ── EDI parsing ───────────────────────────────────────────────────────────────

_ORTHO_PREFIXES = ("D806", "D807", "D808", "D809")


def split_segments(edi_text: str) -> list[list[str]]:
    raw = edi_text.replace("\r\n", "\n").replace("\r", "\n")
    return [seg.split("*") for seg in (s.strip() for s in raw.split("~")) if seg.strip()]


def _normalise_date(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    if len(d) == 8:
        return f"{d[4:6]}/{d[6:8]}/{d[:4]}" if int(d[:4]) >= 1900 else f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return raw


def _cdt(element: str) -> str | None:
    if ":" in element:
        element = element.split(":", 1)[1]
    m = re.search(r"D\d{4}", element)
    return m.group(0) if m else None


def _f(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_cob_edi(edi_text: str) -> dict:
    """
    Pull the COB-relevant fields out of an 837D.

    Walks the transaction in order and uses the SBR segments as a state marker:
    everything after SBR*S belongs to the secondary (destination) plan until an
    SBR*P is hit, after which NM1*PR / AMT / REF segments describe the primary
    plan's prior adjudication (loop 2320).
    """
    segments = split_segments(edi_text)

    out: dict = {
        "subscriber_id": None, "subscriber_name": None, "patient_name": None,
        "provider_npi": None, "provider_name": None,
        "cdt_codes": [], "procedures": [], "procedure_date": None,
        "billed_amount": None,
        "secondary_payer": None, "secondary_payer_id": None,
        "secondary_coinsurance": None, "secondary_settlement": "LUMP_SUM",
        "monthly_cap": None, "term_months": None,
        "primary_payer": None, "primary_payer_id": None,
        "primary_paid": None, "primary_allowed": None,
        "primary_eob_ref": None, "primary_settlement": "LUMP_SUM",
        "has_primary": False, "has_secondary": False,
        "claim_control_no": None,
        # inputs to the COBD liability flowchart
        "patient_relationship": None, "other_relationship": None,
        "other_subscriber_name": None, "subscriber_dob": None,
        "other_subscriber_dob": None, "parents_divorced": False,
        "court_order": None, "restricted_group": False,
    }

    scope = "SECONDARY"   # flips to PRIMARY when the 2320 other-payer loop starts
    REL = {"18": "SELF", "01": "SPOUSE", "19": "CHILD", "20": "CHILD", "G8": "CHILD"}
    sbr_s_rel = None
    cur_nm1 = None

    for seg in segments:
        sid = seg[0] if seg else ""

        if sid == "PAT" and len(seg) > 1:
            out["patient_relationship"] = REL.get(seg[1])

        elif sid == "DMG" and len(seg) > 2 and cur_nm1 == "IL":
            out["subscriber_dob" if scope == "SECONDARY" else "other_subscriber_dob"] = seg[2]

        elif sid == "SBR" and len(seg) > 1:
            kind = seg[1].upper()
            rel = REL.get(seg[2]) if len(seg) > 2 and seg[2] else None
            if kind == "S":
                sbr_s_rel = rel
            else:
                out["other_relationship"] = rel
            if kind == "S":
                scope = "SECONDARY"
                out["has_secondary"] = True
                if len(seg) > 5 and seg[5]:
                    out["secondary_coinsurance"] = int(_f(seg[5]) or 0) or None
            elif kind == "P":
                scope = "PRIMARY"
                out["has_primary"] = True

        elif sid == "NM1" and len(seg) >= 3:
            kind  = seg[1]
            last  = seg[3] if len(seg) > 3 else ""
            first = seg[4] if len(seg) > 4 else ""
            id_q  = seg[8] if len(seg) > 8 else ""
            id_v  = seg[9] if len(seg) > 9 else ""
            cur_nm1 = kind

            if kind == "IL" and scope == "SECONDARY":
                out["subscriber_name"] = f"{first} {last}".strip()
                if id_q == "MI":
                    out["subscriber_id"] = id_v
            elif kind == "IL" and scope == "PRIMARY":
                out["other_subscriber_name"] = f"{first} {last}".strip()
            elif kind == "QC":
                out["patient_name"] = f"{first} {last}".strip()
            elif kind == "85":
                out["provider_name"] = last
                if id_q == "XX":
                    out["provider_npi"] = id_v
            elif kind == "PR":
                if scope == "PRIMARY":
                    out["primary_payer"]    = last
                    out["primary_payer_id"] = id_v or None
                else:
                    out["secondary_payer"]    = last
                    out["secondary_payer_id"] = id_v or None

        elif sid == "CLM" and len(seg) >= 3:
            out["claim_control_no"] = seg[1]
            out["billed_amount"] = _f(seg[2])

        elif sid == "AMT" and len(seg) >= 3 and scope == "PRIMARY":
            qualifier = seg[1].upper()
            if qualifier == "D":          # payer paid amount
                out["primary_paid"] = _f(seg[2])
            elif qualifier == "B6":       # allowed amount
                out["primary_allowed"] = _f(seg[2])

        elif sid == "REF" and len(seg) >= 3:
            qualifier, value = seg[1].upper(), seg[2]
            if qualifier == "F8" and scope == "PRIMARY":
                out["primary_eob_ref"] = value
            elif qualifier == "9F" and value.startswith("PARENTS:"):
                out["parents_divorced"] = value.split(":", 1)[1].upper() in ("DIVORCED", "SEPARATED")
            elif qualifier == "9F" and value.startswith("COURTORDER:"):
                v = value.split(":", 1)[1].upper()
                out["court_order"] = v if v in ("OUR", "OTHER") else None
            elif qualifier == "9F" and value.startswith("GROUP:"):
                out["restricted_group"] = value.split(":", 1)[1].upper() == "RESTRICTED"
            elif qualifier == "9F" and value.startswith("SETTLE:"):
                mode = value.split(":", 1)[1].upper()
                if scope == "PRIMARY":
                    out["primary_settlement"] = mode
                else:
                    out["secondary_settlement"] = mode
            elif qualifier == "G1" and value.startswith("MONTHLYCAP:"):
                out["monthly_cap"] = _f(value.split(":", 1)[1])
            elif qualifier == "G3" and value.startswith("TERMMONTHS:"):
                v = _f(value.split(":", 1)[1])
                out["term_months"] = int(v) if v else None

        elif sid == "DTP" and len(seg) >= 4 and seg[1] == "472" and not out["procedure_date"]:
            out["procedure_date"] = _normalise_date(seg[3])

        elif sid == "SV3" and len(seg) > 1:
            code = _cdt(seg[1])
            fee = _f(seg[2]) if len(seg) > 2 else 0.0
            tooth = seg[5] if len(seg) > 5 else ""
            if code:
                if code not in out["cdt_codes"]:
                    out["cdt_codes"].append(code)
                out["procedures"].append({"cdt_code": code, "fee": fee or 0.0, "tooth": tooth})

    if not out["patient_relationship"] and sbr_s_rel == "SELF":
        out["patient_relationship"] = "SELF"
    return out


# ── Edit routine ──────────────────────────────────────────────────────────────

SUSPEND_CODES = {
    "COB-01": "PRIMARY PAYER EOB NOT ON FILE",
    "COB-02": "PRIMARY PAID EXCEEDS BILLED - OVERPAYMENT RISK",
    "COB-03": "PRIMARY/SECONDARY SETTLEMENT RULES INCOMPATIBLE",
    "COB-04": "SECONDARY COINSURANCE NOT ON FILE",
    "COB-05": "COB LIABILITY - OUR PLAN IS PRIMARY, REPROCESS",
    "COB-06": "COB LIABILITY CANNOT BE DETERMINED - RULE REVIEW",
    "EDI-01": "REQUIRED CLAIM DATA MISSING",
}


def _edit(seq: str, name: str, result: str, detail: str) -> dict:
    return {"seq": seq, "name": name, "result": result, "detail": detail}


def adjudicate_cob(parsed: dict, payer_ctx: dict | None = None) -> dict:
    """
    Run the edit sequence. Returns a decision dict the AS/400 screen renders
    verbatim, including the numbered edit trace.
    """
    trace: list[dict] = []

    billed            = parsed.get("billed_amount")
    primary_paid      = parsed.get("primary_paid")
    primary_allowed   = parsed.get("primary_allowed")
    coins             = parsed.get("secondary_coinsurance")
    prim_mode    = (parsed.get("primary_settlement") or "LUMP_SUM").upper()
    sec_mode     = (parsed.get("secondary_settlement") or "LUMP_SUM").upper()
    cap          = parsed.get("monthly_cap")
    term         = parsed.get("term_months")

    def suspend(code: str, trace_: list[dict], **extra) -> dict:
        return {
            "status": "SUSP",
            "cob_case_type": "CROSS_PLAN_COB",
            "suspend_code": code,
            "reason_code": code,
            "reason_text": SUSPEND_CODES.get(code, "UNCLASSIFIED"),
            "edit_trace": trace_,
            "allowed_amount": None,
            "paid_amount": None,
            "patient_resp": None,
            "remaining_amount": extra.get("remaining"),
            **extra,
        }

    # EDIT 0100 — claim completeness
    if billed is None or not parsed.get("cdt_codes"):
        trace.append(_edit("0100", "CLAIM DATA COMPLETENESS", "FAIL", "BILLED AMT OR CDT CODE MISSING"))
        return suspend("EDI-01", trace)
    trace.append(_edit("0100", "CLAIM DATA COMPLETENESS", "PASS",
                       f"BILLED {billed:,.2f} / {len(parsed['cdt_codes'])} PROC"))

    # EDIT 0220 — other-payer loop present
    if not parsed.get("has_primary") or primary_paid is None:
        trace.append(_edit("0220", "PRIMARY PAYER EOB ON FILE", "FAIL", "LOOP 2320 AMT*D NOT PRESENT"))
        return suspend("COB-01", trace)
    trace.append(_edit("0220", "PRIMARY PAYER EOB ON FILE", "PASS",
                       f"{parsed.get('primary_payer') or 'UNKNOWN'} REF {parsed.get('primary_eob_ref') or '-'}"))

    # EDIT 0230 — COB liability determination (the client's COBD flowchart)
    liab = determine({
        "subscriber_id": parsed.get("subscriber_id"), "cob_flag": True,
        "primary_payer": parsed.get("primary_payer"),
        "primary_paid_amount": primary_paid,
        "primary_eob_ref": parsed.get("primary_eob_ref"),
        "subscriber_name": parsed.get("subscriber_name"),
        "other_subscriber_name": parsed.get("other_subscriber_name"),
        "patient_relationship": parsed.get("patient_relationship"),
        "other_relationship": parsed.get("other_relationship"),
        "subscriber_dob": parsed.get("subscriber_dob"),
        "other_subscriber_dob": parsed.get("other_subscriber_dob"),
        "parents_divorced": parsed.get("parents_divorced"),
        "court_order": parsed.get("court_order"),
        "restricted_group": parsed.get("restricted_group"),
    })
    term_ = liab["terminal"]
    where = f"NODE {term_['node']} {liab['category'].upper()}"
    if liab["hcsc_role"] == "SECONDARY":
        trace.append(_edit("0230", "COB LIABILITY DETERMINATION", "PASS",
                           f"{where} - HCSC SECONDARY"))
    else:
        verdict = "HCSC IS PRIMARY" if liab["hcsc_role"] == "PRIMARY" else "NOT DETERMINABLE"
        trace.append(_edit("0230", "COB LIABILITY DETERMINATION", "FAIL", f"{where} - {verdict}"))
        return suspend(
            "COB-05" if liab["hcsc_role"] == "PRIMARY" else "COB-06", trace,
            cob_case_type="LIABILITY_REVIEW", liability=liab["category"],
            liability_detail=term_.get("detail") or "",
        )

    # EDIT 0310 — primary allowed on file + overpayment guard
    if primary_allowed is None:
        trace.append(_edit("0310", "PRIMARY ALLOWED ON FILE", "FAIL", "AMT*B6 NOT PRESENT"))
        return suspend("COB-01", trace)
    if primary_paid > billed:
        trace.append(_edit("0310", "OVERPAYMENT GUARD", "FAIL",
                           f"PRIMARY PAID {primary_paid:,.2f} GT BILLED {billed:,.2f}"))
        return suspend("COB-02", trace)
    if not coins:
        trace.append(_edit("0450", "SECONDARY COINSURANCE", "FAIL", "SBR COINS PCT NOT ON FILE"))
        return suspend("COB-04", trace)

    ppo_total = (payer_ctx or {}).get("ppo_allowed_total")
    annual_max = (payer_ctx or {}).get("annual_max")
    settle = compute_cob_settlement(
        billed=billed,
        primary_allowed=primary_allowed,
        primary_paid=primary_paid,
        coinsurance_pct=coins,
        hcsc_ppo_allowed_total=ppo_total,
        annual_max=annual_max,
    )
    if not settle.get("ok"):
        trace.append(_edit("0310", "PRIMARY ALLOWED ON FILE", "FAIL", "ALLOWED AMT INVALID"))
        return suspend("COB-01", trace)

    remaining = settle["remaining_cob"]
    secondary_obligation = settle["secondary_owes"]
    trace.append(_edit("0310", "COB REMAINDER", "PASS",
                       f"{primary_allowed:,.2f} ALLOWED − {primary_paid:,.2f} PAID "
                       f"= {remaining:,.2f} REMAINING"))
    trace.append(_edit("0450", "SECONDARY COINSURANCE", "PASS",
                       f"{coins}% OF {remaining:,.2f} = {secondary_obligation:,.2f}"
                       + (f" (FEE/MAX CAP)" if ppo_total or annual_max else ""))))

    # EDIT 0640 — COB settlement reconciliation (the one that matters)
    if prim_mode == sec_mode:
        trace.append(_edit("0640", "COB SETTLEMENT RECONCILIATION", "PASS",
                           f"BOTH PLANS SETTLE {prim_mode} - RULES COMPATIBLE"))
    else:
        max_disbursable = round((cap or 0) * (term or 0), 2)
        detail = (
            f"PRIMARY={prim_mode} SECONDARY={sec_mode} "
            f"CAP {cap or 0:,.2f}/MO X {term or 0} MO = MAX {max_disbursable:,.2f} "
            f"VS OBLIGATION {secondary_obligation:,.2f}"
        )
        trace.append(_edit("0640", "COB SETTLEMENT RECONCILIATION", "FAIL", detail))
        return suspend(
            "COB-03", trace,
            remaining=remaining,
            secondary_obligation=secondary_obligation,
            max_disbursable=max_disbursable,
            shortfall=round(secondary_obligation - max_disbursable, 2),
        )

    # EDIT 0710 — final overpayment verification
    total_paid = round(primary_paid + secondary_obligation, 2)
    if total_paid > billed + 0.01:
        trace.append(_edit("0710", "COMBINED PAYMENT VERIFICATION", "FAIL",
                           f"{total_paid:,.2f} EXCEEDS BILLED {billed:,.2f}"))
        return suspend("COB-02", trace, remaining=remaining)
    trace.append(_edit("0710", "COMBINED PAYMENT VERIFICATION", "PASS",
                       f"{primary_paid:,.2f} + {secondary_obligation:,.2f} = {total_paid:,.2f} LE {billed:,.2f}"))

    patient_resp = round(billed - total_paid, 2)
    trace.append(_edit("0900", "ADJUDICATION COMPLETE", "PASS",
                       f"PAY {secondary_obligation:,.2f} / PAT RESP {patient_resp:,.2f}"))

    return {
        "status": "PAID",
        "cob_case_type": "SIMPLE_COB",
        "suspend_code": None,
        "reason_code": "P100",
        "reason_text": "COB ADJUDICATED - SECONDARY PAYMENT ISSUED",
        "edit_trace": trace,
        "remaining_amount": remaining,
        "allowed_amount": remaining,
        "paid_amount": secondary_obligation,
        "patient_resp": patient_resp,
        "secondary_obligation": secondary_obligation,
    }


def human_review_worksheet(parsed: dict, decision: dict) -> dict:
    """
    The instruction sheet the AS/400 prints for the reviewer when a claim
    suspends on COB-03. This is what the human has to carry out by hand, and
    it is exactly the work the agent system is being asked to take over.
    """
    if decision.get("suspend_code") in ("COB-05", "COB-06"):
        primary_ = parsed.get("primary_payer") or "OTHER PLAN"
        return {
            "why_the_box_failed": (
                f"The COB liability flowchart ended at {decision.get('liability')}. "
                f"{decision.get('liability_detail') or ''} The adjudicator can only pay as "
                f"secondary once the order of liability is settled in HCSC's favour."),
            "arithmetic": [f"Other plan          {primary_}",
                           f"Liability outcome   {decision.get('liability')}"],
            "reviewer_steps": [
                "Open the COBD flowchart and confirm the path taken",
                "Obtain the evidence the rule needs (decree, birth dates, subscriber records)",
                "Reprocess in the correct order of liability",
                "Recover or adjust the other payer's payment if HCSC was primary",
            ],
            "overpayment_safe": True,
            "months_needed": 0,
        }

    billed    = parsed.get("billed_amount") or 0.0
    paid      = parsed.get("primary_paid") or 0.0
    remaining = decision.get("remaining_amount") or round(billed - paid, 2)
    obligation = decision.get("secondary_obligation") or 0.0
    cap        = parsed.get("monthly_cap") or 0.0
    term       = parsed.get("term_months") or 0
    max_disb   = decision.get("max_disbursable") or round(cap * term, 2)
    shortfall  = decision.get("shortfall") or round(obligation - max_disb, 2)
    primary    = parsed.get("primary_payer") or "PRIMARY PAYER"
    eob        = parsed.get("primary_eob_ref") or "EOB REF NOT ON FILE"

    months_needed = (int(obligation // cap) + (1 if obligation % cap else 0)) if cap else 0
    coins = parsed.get("secondary_coinsurance") or 0

    def line(label: str, value: float, note: str = "", sign: str = " ") -> str:
        return f"{label[:36]:<37}{sign}${value:>11,.2f}{('  ' + note) if note else ''}"

    arithmetic = [
        line("Billed charges", billed),
        line(f"Less primary paid ({primary[:14]})", paid, sign="-"),
        line("Remaining balance", remaining),
        line(f"Secondary coinsurance at {coins}%", obligation, "<- owed"),
        line(f"Schedule ceiling {cap:,.2f} x {term} mo", max_disb, "<- disbursable"),
    ]
    if shortfall > 0:
        arithmetic.append(line("Shortfall against schedule", shortfall, "<- exceeds term"))
    else:
        arithmetic.append(line("Schedule headroom", abs(shortfall), "<- clears in term"))

    return {
        "why_the_box_failed": (
            f"{primary} settled this claim with a single lump-sum payment of "
            f"${paid:,.2f}. The secondary plan disburses only on a fixed schedule "
            f"of ${cap:,.2f} per month for {term} months. The adjudicator has no "
            f"rule that converts a lump-sum obligation into a capped monthly "
            f"schedule, so it stopped — even where the arithmetic would work out, "
            f"the conversion itself is not something it is programmed to do."
        ),
        "arithmetic": arithmetic,
        "reviewer_steps": [
            f"Retrieve EOB {eob} from {primary} and confirm paid amount ${paid:,.2f}",
            f"Confirm remaining balance ${billed:,.2f} - ${paid:,.2f} = ${remaining:,.2f}",
            f"Apply secondary coinsurance {parsed.get('secondary_coinsurance') or 0}% -> obligation ${obligation:,.2f}",
            f"Verify no overpayment: ${paid:,.2f} + ${obligation:,.2f} <= ${billed:,.2f}",
            (f"Schedule cannot clear the obligation inside {term} months "
             f"(needs {months_needed} months at ${cap:,.2f}) — override required"
             if shortfall > 0 else
             f"Schedule can clear the obligation in {months_needed} months at ${cap:,.2f}"),
            "Override the monthly disbursement schedule and authorise coordinated settlement",
            "Record COB coordination against both member records",
        ],
        "overpayment_safe": round(paid + obligation, 2) <= round(billed, 2),
        "months_needed": months_needed,
    }
