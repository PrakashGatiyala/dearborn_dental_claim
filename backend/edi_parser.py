"""
EDI 837D parser — pure stdlib, no external dependencies.

Parses X12 005010X224A2 dental claim transactions into:
  - Structured gold-layer fields (same schema as PDF pipeline)
  - Human-readable segment breakdown for Silver-layer display
"""
import re
from datetime import datetime


# ── Segment metadata ──────────────────────────────────────────────────────────

SEGMENT_NAMES = {
    "ISA": "Interchange Control Header",
    "GS":  "Functional Group Header",
    "ST":  "Transaction Set Header",
    "BHT": "Beginning of Hierarchical Transaction",
    "HL":  "Hierarchical Level",
    "PRV": "Provider Information",
    "NM1": "Name",
    "N3":  "Address",
    "N4":  "City / State / ZIP",
    "PER": "Contact Information",
    "REF": "Reference Identification",
    "SBR": "Subscriber Information",
    "DMG": "Demographic Information",
    "CLM": "Claim Information",
    "DTP": "Date / Time Reference",
    "LX":  "Line Counter",
    "SV3": "Dental Service Line",
    "TOO": "Tooth Information",
    "SE":  "Transaction Set Trailer",
    "GE":  "Functional Group Trailer",
    "IEA": "Interchange Control Trailer",
}

NM1_QUALIFIERS = {
    "41": "Submitter",
    "40": "Receiver",
    "85": "Billing Provider",
    "87": "Pay-to Provider",
    "IL": "Insured / Subscriber",
    "QC": "Patient",
    "PR": "Payer",
    "77": "Service Facility",
}

DTP_QUALIFIERS = {
    "472": "Date of Service",
    "431": "Onset / Accident Date",
    "096": "Discharge Date",
    "439": "Accident Date",
}

REF_QUALIFIERS = {
    "EI":  "Tax ID",
    "6R":  "Tooth Reference",
    "G1":  "Predetermination Number",
    "9F":  "Referral Number",
    "D9":  "Claim Identifier",
    "1D":  "Medicaid Member ID",
    "SY":  "Social Security Number",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_segments(edi_text: str) -> list[list[str]]:
    """Split raw EDI text into parsed segments (list of element lists)."""
    raw = edi_text.replace("\r\n", "\n").replace("\r", "\n")
    parts = [s.strip() for s in raw.split("~") if s.strip()]
    return [seg.split("*") for seg in parts]


def _normalise_date(raw: str) -> str:
    """
    Convert EDI date to MM/DD/YYYY display format.
    Handles both YYYYMMDD and MMDDYYYY (common in synthetic files).
    """
    d = re.sub(r"\D", "", raw)
    if len(d) == 8:
        # Heuristic: if first 4 digits look like a year (>= 1900) → YYYYMMDD
        if int(d[:4]) >= 1900:
            return f"{d[4:6]}/{d[6:8]}/{d[:4]}"
        else:
            # MMDDYYYY
            return f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return raw


def _cdt_from_sv3(element: str) -> str | None:
    """Extract D-code from SV3 element[1]: 'AD:D2740' → 'D2740'."""
    if ":" in element:
        element = element.split(":", 1)[1]
    m = re.search(r"D\d{4}", element)
    return m.group(0) if m else None


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_837d(edi_text: str) -> dict:
    """
    Parse an EDI 837D transaction and return gold-compatible structured fields.

    Returns dict with the same key names used by medallion.py's process_gold().
    """
    segments = _split_segments(edi_text)

    subscriber_id    = None
    subscriber_name  = None
    patient_name     = None
    payer_name       = None
    provider_npi     = None
    provider_name    = None
    cdt_codes        = []
    procedure_date   = None
    billed_amount    = None
    predet_number    = None
    procedures       = []

    # COB: an 837D carries the destination plan in the SBR*S loop and the plan
    # that already paid in the SBR*P other-payer loop (2320). Both present means
    # this is a coordination-of-benefits claim.
    has_secondary          = False
    has_primary            = False
    primary_payer          = None
    primary_paid           = None
    primary_allowed        = None
    primary_eob_ref        = None
    primary_settlement     = "LUMP_SUM"
    secondary_settlement   = "LUMP_SUM"
    secondary_coinsurance  = None
    monthly_cap            = None
    term_months            = None
    scope                  = "SECONDARY"

    # COBD (liability determination) inputs
    REL = {"18": "SELF", "01": "SPOUSE", "19": "CHILD", "20": "CHILD", "G8": "CHILD"}
    sbr_s_rel = None                # SBR02 on our plan
    sbr_p_rel = None                # SBR02 on the other-payer loop
    pat_rel = None                  # PAT01
    other_subscriber_name = None
    subscriber_dob = None
    other_subscriber_dob = None
    parents_divorced = False
    court_order = None
    restricted_group = False

    current_nm1_type = None

    for seg in segments:
        sid = seg[0] if seg else ""

        if sid == "PAT" and len(seg) > 1:
            pat_rel = REL.get(seg[1])

        elif sid == "DMG" and len(seg) > 2 and current_nm1_type == "IL":
            if scope == "SECONDARY":
                subscriber_dob = seg[2]
            else:
                other_subscriber_dob = seg[2]

        elif sid == "SBR" and len(seg) > 1:
            # SBR*S = destination (secondary) plan, SBR*P = other-payer loop 2320.
            # Everything that follows belongs to whichever loop we are in.
            kind = seg[1].upper()
            rel = REL.get(seg[2]) if len(seg) > 2 and seg[2] else None
            if kind == "S":
                sbr_s_rel = rel
            elif kind == "P":
                sbr_p_rel = rel
            if kind == "S":
                scope, has_secondary = "SECONDARY", True
                if len(seg) > 5 and seg[5]:
                    try:
                        secondary_coinsurance = int(float(seg[5])) or None
                    except ValueError:
                        pass
            elif kind == "P":
                scope, has_primary = "PRIMARY", True

        elif sid == "NM1" and len(seg) >= 3:
            current_nm1_type = seg[1]
            last   = seg[3] if len(seg) > 3 else ""
            first  = seg[4] if len(seg) > 4 else ""
            id_qual = seg[8] if len(seg) > 8 else ""
            id_val  = seg[9] if len(seg) > 9 else ""

            if current_nm1_type == "IL" and scope == "SECONDARY":
                # Subscriber: NM1*IL*1*LastName*FirstName****MI*ID
                subscriber_name = f"{first} {last}".strip()
                if id_qual == "MI":
                    subscriber_id = id_val

            elif current_nm1_type == "IL" and scope == "PRIMARY":
                other_subscriber_name = f"{first} {last}".strip()

            elif current_nm1_type == "QC":
                # Patient (the treated dependent): NM1*QC*1*Last*First
                patient_name = f"{first} {last}".strip()

            elif current_nm1_type == "85":
                # Billing provider
                provider_name = last  # org name is in element[3] for type=2
                if id_qual == "XX":
                    provider_npi = id_val

            elif current_nm1_type == "PR":
                if scope == "PRIMARY":
                    primary_payer = last
                else:
                    payer_name = last

        elif sid == "AMT" and len(seg) >= 3 and scope == "PRIMARY":
            # What the primary plan already paid / allowed
            try:
                if seg[1].upper() == "D":
                    primary_paid = float(seg[2])
                elif seg[1].upper() == "B6":
                    primary_allowed = float(seg[2])
            except ValueError:
                pass

        elif sid == "CLM" and len(seg) >= 3:
            try:
                billed_amount = float(seg[2])
            except (ValueError, IndexError):
                pass

        elif sid == "DTP" and len(seg) >= 4:
            if seg[1] == "472":  # Date of Service
                procedure_date = _normalise_date(seg[3])

        elif sid == "SV3" and len(seg) >= 3:
            code = _cdt_from_sv3(seg[1]) if len(seg) > 1 else None
            tooth = seg[7] if len(seg) > 7 else ""
            try:
                fee = float(seg[2])
            except (ValueError, IndexError):
                fee = 0.0
            if code:
                if code not in cdt_codes:
                    cdt_codes.append(code)
                procedures.append({
                    "cdt_code": code,
                    "fee": fee,
                    "tooth_number": tooth or "",
                    "surface": seg[3] if len(seg) > 3 else "",
                })

        elif sid == "REF" and len(seg) >= 3:
            qual, val = seg[1].upper(), seg[2]

            if qual == "F8" and scope == "PRIMARY":
                primary_eob_ref = val
            elif qual == "9F" and val.startswith("PARENTS:"):
                parents_divorced = val.split(":", 1)[1].upper() in ("DIVORCED", "SEPARATED")
            elif qual == "9F" and val.startswith("COURTORDER:"):
                v = val.split(":", 1)[1].upper()
                court_order = v if v in ("OUR", "OTHER") else None
            elif qual == "9F" and val.startswith("GROUP:"):
                restricted_group = val.split(":", 1)[1].upper() == "RESTRICTED"
            elif qual == "9F" and val.startswith("SETTLE:"):
                mode = val.split(":", 1)[1].upper()
                if scope == "PRIMARY":
                    primary_settlement = mode
                else:
                    secondary_settlement = mode
            elif qual == "G1" and val.startswith("MONTHLYCAP:"):
                try:
                    monthly_cap = float(val.split(":", 1)[1])
                except ValueError:
                    pass
            elif qual == "G3" and val.startswith("TERMMONTHS:"):
                try:
                    term_months = int(float(val.split(":", 1)[1]))
                except ValueError:
                    pass
            elif qual in ("G1", "9F"):
                # Plain G1/9F without a COB prefix is a predetermination number
                predet_number = val

    # x-ray present if any diagnostic/imaging D-code found
    xray_present = any(re.match(r"D0\d{3}", c) for c in cdt_codes)

    return {
        "subscriber_id":           subscriber_id,
        "subscriber_name":         subscriber_name,
        "patient_name":            patient_name or subscriber_name,
        "payer_name":              payer_name,
        "provider_npi":            provider_npi,
        "provider_name":           provider_name,
        "cdt_codes":               cdt_codes,
        "procedure_date":          procedure_date,
        "billed_amount":           billed_amount,
        "predetermination_number": predet_number,
        "xray_present":            xray_present,

        # COB — true when the claim carries both a destination plan (SBR*S) and
        # an other-payer loop showing a plan that already paid (SBR*P).
        "cob_flag":                has_secondary and has_primary,
        "primary_payer":           primary_payer,
        "primary_paid_amount":     primary_paid,
        "primary_allowed_amount":  primary_allowed,
        "primary_eob_ref":         primary_eob_ref,
        "primary_settlement":      primary_settlement,
        "secondary_settlement":    secondary_settlement,
        "secondary_coinsurance":   secondary_coinsurance,
        "monthly_cap":             monthly_cap,
        "term_months":             term_months,

        # Inputs to the COBD liability flowchart (cobd.py)
        "patient_relationship":    pat_rel or ("SELF" if sbr_s_rel == "SELF" else None),
        "other_relationship":      sbr_p_rel,
        "other_subscriber_name":   other_subscriber_name,
        "subscriber_dob":          subscriber_dob,
        "other_subscriber_dob":    other_subscriber_dob,
        "parents_divorced":        parents_divorced,
        "court_order":             court_order,
        "restricted_group":        restricted_group,

        "procedures":              procedures,
        "edi_segment_count":       len(segments),
    }


def edi_to_readable(edi_text: str) -> list[dict]:
    """
    Convert EDI 837D text into a list of human-readable segment dicts for UI display.

    Each dict: { id, name, qualifier_context, description, elements }
    """
    segments = _split_segments(edi_text)
    readable = []

    current_nm1_type = None

    for seg in segments:
        if not seg:
            continue
        sid = seg[0]
        name = SEGMENT_NAMES.get(sid, sid)
        qualifier_context = None
        description = ""
        elements = seg[1:]

        if sid == "ISA":
            description = (
                f"Interchange: sender={seg[6].strip() if len(seg)>6 else '?'} "
                f"→ receiver={seg[8].strip() if len(seg)>8 else '?'}"
            )
        elif sid == "GS":
            description = f"Functional group: {seg[1] if len(seg)>1 else ''}, date {seg[4] if len(seg)>4 else ''}"
        elif sid == "ST":
            description = "837 Dental claim transaction begins"
        elif sid == "BHT":
            ref = seg[3] if len(seg) > 3 else ""
            description = f"Claim reference: {ref}"
        elif sid == "NM1":
            current_nm1_type = seg[1] if len(seg) > 1 else ""
            qualifier_context = NM1_QUALIFIERS.get(current_nm1_type, current_nm1_type)
            last  = seg[3] if len(seg) > 3 else ""
            first = seg[4] if len(seg) > 4 else ""
            id_v  = seg[9] if len(seg) > 9 else ""
            full  = f"{first} {last}".strip() if first else last
            description = f"{qualifier_context}: {full}" + (f" | ID: {id_v}" if id_v else "")
        elif sid == "N3":
            description = f"Address: {seg[1] if len(seg)>1 else ''}"
        elif sid == "PER":
            description = f"Contact: {seg[2] if len(seg)>2 else ''}"
        elif sid == "SBR":
            description = f"Subscriber: group {seg[3] if len(seg)>3 else ''}, relationship {seg[2] if len(seg)>2 else ''}"
        elif sid == "DMG":
            dob = _normalise_date(seg[2]) if len(seg) > 2 else ""
            gender = {"M": "Male", "F": "Female", "U": "Unknown"}.get(seg[3] if len(seg)>3 else "U", "Unknown")
            description = f"DOB: {dob}, Gender: {gender}"
        elif sid == "CLM":
            ref  = seg[1] if len(seg) > 1 else ""
            amt  = seg[2] if len(seg) > 2 else ""
            description = f"Claim ID: {ref} | Total billed: ${float(amt):,.2f}" if amt else f"Claim ID: {ref}"
        elif sid == "DTP":
            qual = seg[1] if len(seg) > 1 else ""
            date = _normalise_date(seg[3]) if len(seg) > 3 else ""
            qualifier_context = DTP_QUALIFIERS.get(qual, qual)
            description = f"{qualifier_context}: {date}"
        elif sid == "LX":
            description = f"Service line {seg[1] if len(seg)>1 else ''}"
        elif sid == "SV3":
            code  = _cdt_from_sv3(seg[1]) if len(seg) > 1 else ""
            fee   = seg[2] if len(seg) > 2 else ""
            tooth = seg[7] if len(seg) > 7 else ""
            fee_fmt = f"${float(fee):,.2f}" if fee else ""
            description = (
                f"Procedure: {code}"
                + (f" | Fee: {fee_fmt}" if fee_fmt else "")
                + (f" | Tooth: {tooth}" if tooth else "")
            )
        elif sid == "REF":
            qual = seg[1] if len(seg) > 1 else ""
            val  = seg[2] if len(seg) > 2 else ""
            qualifier_context = REF_QUALIFIERS.get(qual, qual)
            description = f"{qualifier_context}: {val}"
        elif sid == "HL":
            description = f"Hierarchical level {seg[1] if len(seg)>1 else ''}"
        elif sid == "SE":
            description = f"End of transaction — {seg[1] if len(seg)>1 else ''} segments"
        elif sid in ("GE", "IEA"):
            description = "End of functional group / interchange"
        else:
            description = " | ".join(e for e in elements if e)

        readable.append({
            "id":                sid,
            "name":              name,
            "qualifier_context": qualifier_context,
            "description":       description,
            "elements":          elements,
        })

    return readable
