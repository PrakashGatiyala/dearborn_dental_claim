"""
Medallion pipeline: Bronze → Silver → Gold

Bronze  — raw PDF / EDI bytes
Silver  — text extracted from each PDF (or EDI segments), as JSON
Gold    — structured claim fields parsed from silver, as JSON

All three layers live in the Postgres `claim_files` table (see blobstore.py).
Nothing is written to disk.
"""
import json
import os
import re
import tempfile
from datetime import datetime, timezone

import blobstore
from database import SessionLocal, Claim
from extract_text import extract_pdf_to_string


# ── Bronze ────────────────────────────────────────────────────────────────────

def process_bronze(claim_bytes: bytes, policy_bytes: bytes, filename: str | None = None) -> str:
    """
    Save raw uploaded PDFs. Creates the Claim row in the DB.
    Returns the new claim_id.
    """
    db = SessionLocal()
    count = db.query(Claim).count()
    claim_id = f"CLM-{count + 1:04d}"
    db.close()

    blobstore.put(claim_id, "bronze", "claim.pdf", claim_bytes)
    blobstore.put(claim_id, "bronze", "policy.pdf", policy_bytes)

    meta = {
        "claim_id": claim_id,
        "upload_ts": datetime.now(timezone.utc).isoformat(),
        "claim_size_bytes": len(claim_bytes),
        "policy_size_bytes": len(policy_bytes),
    }
    blobstore.put_json(claim_id, "bronze", "meta.json", meta)

    db = SessionLocal()
    db.add(Claim(claim_id=claim_id, status="UPLOADED",
                 bronze_path=blobstore.marker("bronze", claim_id)))
    db.commit()
    db.close()

    print(f"[Bronze] claim_id={claim_id} saved to Postgres")
    return claim_id


# ── Silver ────────────────────────────────────────────────────────────────────

def process_silver(claim_id: str) -> dict:
    """
    Extract text from both PDFs in the bronze folder.
    Saves extracted.json to the silver folder.
    Returns the silver data dict.
    """
    def _extract(filename: str) -> dict:
        pdf = blobstore.get_bytes(claim_id, "bronze", filename)
        if pdf is None:
            return {"text": "", "page_count": 0, "method": "none"}
        # The extractor wants a path, so give it a temp file that is deleted
        # straight away — nothing is kept on disk.
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            tmp.write(pdf)
            tmp.close()
            text, method = extract_pdf_to_string(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
        # page_count derived from text sections rather than re-opening the PDF
        page_count = text.count("\x0c") + 1 if text else 0
        return {"text": text, "page_count": page_count, "method": method}

    silver_data = {
        "claim_id": claim_id,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "claim_pdf": _extract("claim.pdf"),
        "policy_pdf": _extract("policy.pdf"),
    }

    blobstore.put_json(claim_id, "silver", "extracted.json", silver_data)

    db = SessionLocal()
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    claim.status = "SILVER_DONE"
    claim.silver_path = blobstore.marker("silver", claim_id)
    db.commit()
    db.close()

    print(f"[Silver] claim_id={claim_id} text extracted")
    return silver_data


# ── Gold ──────────────────────────────────────────────────────────────────────

def process_gold(claim_id: str) -> dict:
    """
    Parse the silver text into structured claim fields.
    Saves structured.json to the gold folder.
    Returns the gold data dict.
    """
    silver_data = blobstore.get_json(claim_id, "silver", "extracted.json")

    claim_text = silver_data["claim_pdf"]["text"]
    policy_text = silver_data["policy_pdf"]["text"]
    combined = claim_text + "\n" + policy_text

    def _first(pattern: str, text: str, flags: int = 0):
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else None

    def _all(pattern: str, text: str):
        return re.findall(pattern, text)

    # Subscriber ID — format: HCSC-TX-88301124
    subscriber_id = _first(r"Subscriber ID\s*\n([A-Z]+-[A-Z]+-\d+)", claim_text)

    # All CDT codes in the claim (D followed by 4 digits)
    cdt_codes = list(dict.fromkeys(_all(r"\b(D\d{4})\b", claim_text)))

    # Date of Service — MM/DD/YYYY
    dos_raw = _first(r"Date of Service\s*\n(\d{2}/\d{2}/\d{4})", claim_text)

    # NPI — 10-digit number after "NPI Number"
    npi = _first(r"NPI Number\s*\n(\d{10})", claim_text)

    # Provider name
    provider_name = _first(r"Provider Name\s*\n(.+)", claim_text)

    # Total billed amount — grab the last $ value (usually the total)
    amounts = _all(r"\$[\d,]+\.?\d*", claim_text)
    billed_amount = None
    if amounts:
        # Parse and take the largest value as the total billed
        parsed = []
        for a in amounts:
            try:
                parsed.append(float(a.replace("$", "").replace(",", "")))
            except ValueError:
                pass
        billed_amount = max(parsed) if parsed else None

    # Predetermination number — e.g. PDET-2025-008812
    predet = _first(r"(PDET[-\d]+)", combined)

    # X-ray present — any mention in either document
    xray_present = bool(re.search(r"(?i)(x.?ray|radiograph|bitewing|periapical)", combined))

    # COB flag — secondary coverage listed and is not "None"
    cob_match = _first(r"Secondary Coverage\s*\n(.+)", claim_text)
    cob_flag = bool(cob_match and cob_match.strip().lower() not in ("none", "n/a", ""))

    gold_data = {
        "claim_id": claim_id,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "subscriber_id": subscriber_id,
        "cdt_codes": cdt_codes,
        "procedure_date": dos_raw,
        "billed_amount": billed_amount,
        "provider_npi": npi,
        "provider_name": provider_name,
        "predetermination_number": predet,
        "xray_present": xray_present,
        "cob_flag": cob_flag,
        "deductible_met": False,  # conservative default — agent accounts for this
    }

    blobstore.put_json(claim_id, "gold", "structured.json", gold_data)

    db = SessionLocal()
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    claim.status = "GOLD_DONE"
    claim.gold_path = blobstore.marker("gold", claim_id)
    db.commit()
    db.close()

    print(f"[Gold] claim_id={claim_id} parsed: subscriber={subscriber_id}, codes={cdt_codes}")
    return gold_data


# ── EDI pipeline (Bronze → Silver → Gold for 837D input) ─────────────────────

def process_bronze_edi(edi_bytes: bytes, filename: str | None = None) -> str:
    """Save raw EDI transmission. Creates the Claim row. Returns claim_id."""
    db = SessionLocal()
    count = db.query(Claim).count()
    claim_id = f"CLM-{count + 1:04d}"
    db.close()

    blobstore.put(claim_id, "bronze", "transmission.edi", edi_bytes)

    meta = {
        "claim_id":        claim_id,
        "upload_ts":       datetime.now(timezone.utc).isoformat(),
        "input_type":      "edi",
        "edi_filename":    filename or "transmission.edi",
        "edi_size_bytes":  len(edi_bytes),
    }
    blobstore.put_json(claim_id, "bronze", "meta.json", meta)

    db = SessionLocal()
    db.add(Claim(claim_id=claim_id, status="UPLOADED",
                 bronze_path=blobstore.marker("bronze", claim_id)))
    db.commit()
    db.close()

    print(f"[Bronze/EDI] claim_id={claim_id} saved {len(edi_bytes)} bytes")
    return claim_id


def process_silver_edi(claim_id: str) -> dict:
    """Parse EDI segments into human-readable form. Saves extracted.json."""
    from edi_parser import edi_to_readable

    edi_text = blobstore.get_text(claim_id, "bronze", "transmission.edi") or ""

    segments = edi_to_readable(edi_text)

    silver_data = {
        "claim_id":      claim_id,
        "extracted_at":  datetime.now(timezone.utc).isoformat(),
        "input_type":    "edi",
        "edi": {
            "present":       True,
            "segment_count": len(segments),
            "segments":      segments,
            "raw_preview":   edi_text[:800],
        },
    }

    blobstore.put_json(claim_id, "silver", "extracted.json", silver_data)

    db = SessionLocal()
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    claim.status = "SILVER_DONE"
    claim.silver_path = blobstore.marker("silver", claim_id)
    db.commit()
    db.close()

    print(f"[Silver/EDI] claim_id={claim_id} — {len(segments)} segments parsed")
    return silver_data


def process_gold_edi(claim_id: str) -> dict:
    """Extract structured claim fields from EDI silver data. Saves structured.json."""
    from edi_parser import parse_837d

    edi_text = blobstore.get_text(claim_id, "bronze", "transmission.edi") or ""

    parsed = parse_837d(edi_text)

    gold_data = {
        "claim_id":                claim_id,
        "parsed_at":               datetime.now(timezone.utc).isoformat(),
        "input_type":              "edi",
        "subscriber_id":           parsed.get("subscriber_id"),
        "subscriber_name":         parsed.get("subscriber_name"),
        "patient_name":            parsed.get("patient_name"),
        "payer_name":              parsed.get("payer_name"),
        "cdt_codes":               parsed.get("cdt_codes", []),
        "procedure_date":          parsed.get("procedure_date"),
        "billed_amount":           parsed.get("billed_amount"),
        "provider_npi":            parsed.get("provider_npi"),
        "provider_name":           parsed.get("provider_name"),
        "predetermination_number": parsed.get("predetermination_number"),
        "xray_present":            parsed.get("xray_present", False),
        "deductible_met":          False,

        # Coordination of benefits — what the primary plan already settled and
        # how each plan disburses. The agent needs all of this for Scenario 3.
        "cob_flag":                parsed.get("cob_flag", False),
        "primary_payer":           parsed.get("primary_payer"),
        "primary_paid_amount":     parsed.get("primary_paid_amount"),
        "primary_allowed_amount":  parsed.get("primary_allowed_amount"),
        "primary_eob_ref":         parsed.get("primary_eob_ref"),
        "primary_settlement":      parsed.get("primary_settlement"),
        "secondary_settlement":    parsed.get("secondary_settlement"),
        "secondary_coinsurance":   parsed.get("secondary_coinsurance"),
        "monthly_cap":             parsed.get("monthly_cap"),
        "term_months":             parsed.get("term_months"),

        # COBD liability-flow inputs
        "patient_relationship":    parsed.get("patient_relationship"),
        "other_relationship":      parsed.get("other_relationship"),
        "other_subscriber_name":   parsed.get("other_subscriber_name"),
        "subscriber_dob":          parsed.get("subscriber_dob"),
        "other_subscriber_dob":    parsed.get("other_subscriber_dob"),
        "parents_divorced":        parsed.get("parents_divorced", False),
        "court_order":             parsed.get("court_order"),
        "restricted_group":        parsed.get("restricted_group", False),

        "procedures":              parsed.get("procedures", []),
    }

    blobstore.put_json(claim_id, "gold", "structured.json", gold_data)

    db = SessionLocal()
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    claim.status = "GOLD_DONE"
    claim.gold_path = blobstore.marker("gold", claim_id)
    db.commit()
    db.close()

    print(f"[Gold/EDI] claim_id={claim_id} subscriber={gold_data['subscriber_id']}, codes={gold_data['cdt_codes']}")
    return gold_data
