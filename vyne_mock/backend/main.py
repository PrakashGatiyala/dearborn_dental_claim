"""
Vyne Dental Mock Gateway — a clearinghouse, nothing more.

Backend : http://localhost:8001
Portal  : http://localhost:5174

Vyne does NOT adjudicate. It receives an 837D from the practice, validates the
envelope, acknowledges it, and forwards it to the payer's adjudication system.
Everything about whether the claim pays, suspends, or needs a human happens
downstream on the AS/400.

    RECEIVED  →  ACKNOWLEDGED  →  FORWARDED      (envelope valid, sent to payer)
    RECEIVED  →  REJECTED                        (envelope malformed, never sent)

Chain:

    vyne_sender.py  ──►  VYNE (:8001)  ──►  AS/400 (:8002)  ──►  DEARBORN (:8000)
                         this service       adjudicates          agent works the
                                            COB claims           suspended ones
"""
import json
import os
import random
import re
import string
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import VyneClaim, create_tables, get_db


# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    print("✅ Vyne Dental mock database ready")
    threading.Thread(target=_status_progression_loop, daemon=True).start()
    yield


app = FastAPI(title="Vyne Dental Mock Gateway", version="2.0.0", lifespan=lifespan)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174")
_origins = [o.strip().rstrip("/") for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_AS400_API_URL    = os.getenv("AS400_API_URL",    "http://localhost:8002")
_AS400_PORTAL_URL = os.getenv("AS400_PORTAL_URL", "http://localhost:5175")
_VYNE_PORTAL_URL  = os.getenv("VYNE_PORTAL_URL",  "http://localhost:5174")


# ── EDI parsing (envelope-level only — Vyne reads just enough to route) ───────

def _split_segments(edi_text: str) -> list[list[str]]:
    raw = edi_text.replace("\r\n", "\n").replace("\r", "\n")
    return [seg.split("*") for seg in (s.strip() for s in raw.split("~")) if seg.strip()]


def _normalise_date(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    if len(d) == 8:
        return f"{d[4:6]}/{d[6:8]}/{d[:4]}" if int(d[:4]) >= 1900 else f"{d[:2]}/{d[2:4]}/{d[4:]}"
    return raw


def _cdt_from_sv3(element: str) -> str | None:
    if ":" in element:
        element = element.split(":", 1)[1]
    m = re.search(r"D\d{4}", element)
    return m.group(0) if m else None


def parse_edi(edi_text: str) -> dict:
    """Pull routing-level fields. Scope flips at SBR*P into the other-payer loop."""
    segments = _split_segments(edi_text)
    subscriber_id = subscriber_name = payer_name = payer_id = None
    patient_name = provider_npi = provider_name = None
    primary_payer = None
    cdt_codes: list[str] = []
    procedure_date = billed_amount = None
    procedures: list[dict] = []
    has_secondary = has_primary = False
    scope = "SECONDARY"

    for seg in segments:
        sid = seg[0] if seg else ""

        if sid == "SBR" and len(seg) > 1:
            kind = seg[1].upper()
            if kind == "S":
                scope, has_secondary = "SECONDARY", True
            elif kind == "P":
                scope, has_primary = "PRIMARY", True

        elif sid == "NM1" and len(seg) >= 3:
            nm1_type = seg[1]
            last  = seg[3] if len(seg) > 3 else ""
            first = seg[4] if len(seg) > 4 else ""
            id_q  = seg[8] if len(seg) > 8 else ""
            id_v  = seg[9] if len(seg) > 9 else ""
            if nm1_type == "IL" and scope == "SECONDARY":
                subscriber_name = f"{first} {last}".strip()
                if id_q == "MI":
                    subscriber_id = id_v
            elif nm1_type == "QC":
                patient_name = f"{first} {last}".strip()
            elif nm1_type == "85":
                provider_name = last
                if id_q == "XX":
                    provider_npi = id_v
            elif nm1_type == "PR":
                if scope == "PRIMARY":
                    primary_payer = last
                else:
                    payer_name, payer_id = last, (id_v or None)

        elif sid == "CLM" and len(seg) >= 3:
            try:
                billed_amount = float(seg[2])
            except (ValueError, IndexError):
                pass

        elif sid == "DTP" and len(seg) >= 4 and seg[1] == "472" and procedure_date is None:
            procedure_date = _normalise_date(seg[3])

        elif sid == "SV3" and len(seg) > 1:
            code = _cdt_from_sv3(seg[1])
            try:
                fee = float(seg[2])
            except (ValueError, IndexError):
                fee = 0.0
            tooth = seg[5] if len(seg) > 5 else ""
            if code:
                if code not in cdt_codes:
                    cdt_codes.append(code)
                procedures.append({"cdt_code": code, "fee": fee, "tooth": tooth})

    return {
        "subscriber_id":   subscriber_id,
        "subscriber_name": subscriber_name,
        "patient_name":    patient_name or subscriber_name,
        "payer_name":      payer_name,
        "payer_id":        payer_id,
        "primary_payer":   primary_payer,
        "provider_npi":    provider_npi,
        "provider_name":   provider_name,
        "cdt_codes":       cdt_codes,
        "procedure_date":  procedure_date,
        "billed_amount":   billed_amount,
        "procedures":      procedures,
        "has_secondary":   has_secondary,
        "has_primary":     has_primary,
    }


# ── Envelope validation ───────────────────────────────────────────────────────

def _envelope_errors(raw: str, parsed: dict) -> list[str]:
    """
    The only judgement Vyne makes: is this a well-formed 837D it can route?
    Nothing here looks at benefits — that is the payer's job.
    """
    errors: list[str] = []
    seg_ids = {s[0] for s in _split_segments(raw) if s}

    if "ISA" not in seg_ids:
        errors.append("MISSING ISA INTERCHANGE HEADER")
    if "ST" not in seg_ids:
        errors.append("MISSING ST TRANSACTION SET HEADER")
    if "CLM" not in seg_ids:
        errors.append("MISSING CLM CLAIM SEGMENT")
    if parsed.get("billed_amount") is None:
        errors.append("CLM BILLED AMOUNT NOT NUMERIC")
    if not parsed.get("cdt_codes"):
        errors.append("NO SERVICE LINES PRESENT")
    return errors


# ── Tracking ID ───────────────────────────────────────────────────────────────

def _new_tracking_id() -> str:
    return "VYN-" + "".join(random.choices(string.digits, k=8))


# ── Status progression (background thread) ────────────────────────────────────

RESPONSE_CODES = {
    "ACKNOWLEDGED": ("A1",  "999 acknowledgement returned — envelope accepted"),
    "FORWARDED":    ("A2",  "Claim forwarded to payer adjudication system"),
    "REJECTED":     ("R3",  "EDI envelope error — claim not forwarded"),
}

_DELAYS = {"RECEIVED": 8, "ACKNOWLEDGED": 8}
_TERMINAL = {"FORWARDED", "REJECTED"}


def _forward_to_as400(claim: VyneClaim) -> tuple[bool, str]:
    """Hand the claim to the payer's AS/400 adjudication system."""
    if not claim.raw_edi:
        return False, "no raw EDI stored"
    try:
        resp = requests.post(
            f"{_AS400_API_URL}/as400/claims/receive",
            files={"edi_file": (claim.filename or "claim.edi",
                               claim.raw_edi.encode(), "text/plain")},
            data={"vyne_id": claim.tracking_id},
            timeout=20,
        )
    except Exception as exc:                       # noqa: BLE001
        return False, str(exc)

    if not resp.ok:
        return False, f"HTTP {resp.status_code}"

    data = resp.json()
    claim.as400_claim_no   = data.get("claim_no")
    claim.as400_screen_url = data.get("screen_url") or f"{_AS400_PORTAL_URL}/claim/{data.get('claim_no')}"
    return True, claim.as400_claim_no or ""


def _advance_status(claim: VyneClaim, db: Session):
    if claim.status in _TERMINAL:
        return

    if claim.status == "RECEIVED":
        errors = json.loads(claim.envelope_errors or "[]")
        if errors:
            claim.status = "REJECTED"
            claim.response_code, claim.response_message = RESPONSE_CODES["REJECTED"]
            claim.response_message = f"{claim.response_message}: {'; '.join(errors)}"
            print(f"[Vyne] {claim.tracking_id} → REJECTED ({errors[0]})")
        else:
            claim.status = "ACKNOWLEDGED"
            claim.response_code, claim.response_message = RESPONSE_CODES["ACKNOWLEDGED"]
            print(f"[Vyne] {claim.tracking_id} → ACKNOWLEDGED")

    elif claim.status == "ACKNOWLEDGED":
        ok, info = _forward_to_as400(claim)
        if ok:
            claim.status = "FORWARDED"
            claim.response_code, claim.response_message = RESPONSE_CODES["FORWARDED"]
            claim.forwarded_at = datetime.now(timezone.utc)
            print(f"[Vyne→AS/400] {claim.tracking_id} → {info}")
        else:
            # Stay ACKNOWLEDGED and retry on the next sweep — the payer system
            # may simply not be up yet.
            claim.response_message = f"Awaiting payer system — forward failed: {info}"
            print(f"[Vyne→AS/400] forward failed for {claim.tracking_id}: {info}")

    claim.updated_at = datetime.now(timezone.utc)
    db.commit()


def _status_progression_loop():
    from database import SessionLocal
    while True:
        time.sleep(5)
        db = SessionLocal()
        try:
            pending = db.query(VyneClaim).filter(
                VyneClaim.status.notin_(list(_TERMINAL))
            ).all()
            now = datetime.now(timezone.utc)
            for claim in pending:
                delay = _DELAYS.get(claim.status, 9999)
                updated = claim.updated_at or now
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if (now - updated).total_seconds() >= delay:
                    _advance_status(claim, db)
        except Exception as exc:                   # noqa: BLE001
            print(f"[progression] error: {exc}")
        finally:
            db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/v1/health")
def health():
    return {"status": "ok", "service": "vyne-dental-mock", "role": "clearinghouse"}


@app.post("/v1/claims/submit")
async def submit_claim(
    edi_file: UploadFile = File(...),
    details: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    raw = (await edi_file.read()).decode("utf-8", errors="replace")
    # Supporting documents are optional and must never block a claim.
    try:
        details_json = json.dumps(json.loads(details)) if details else None
    except ValueError:
        details_json = None
    parsed = parse_edi(raw)
    errors = _envelope_errors(raw, parsed)
    tracking_id = _new_tracking_id()
    now = datetime.now(timezone.utc)

    claim = VyneClaim(
        tracking_id      = tracking_id,
        submission_date  = now.strftime("%Y-%m-%d"),
        payer_id         = parsed.get("payer_id"),
        payer_name       = parsed.get("payer_name"),
        primary_payer    = parsed.get("primary_payer"),
        subscriber_id    = parsed.get("subscriber_id"),
        subscriber_name  = parsed.get("subscriber_name"),
        provider_npi     = parsed.get("provider_npi"),
        provider_name    = parsed.get("provider_name"),
        patient_name     = parsed.get("patient_name"),
        cdt_codes        = json.dumps(parsed.get("cdt_codes", [])),
        procedure_date   = parsed.get("procedure_date"),
        billed_amount    = parsed.get("billed_amount"),
        is_cob           = bool(parsed.get("has_secondary") and parsed.get("has_primary")),
        status           = "RECEIVED",
        response_code    = "R0",
        response_message = "Claim received — envelope validation queued",
        envelope_errors  = json.dumps(errors),
        raw_edi          = raw[:20000],
        procedures       = json.dumps(parsed.get("procedures", [])),
        filename         = edi_file.filename,
        patient_details  = details_json,
        created_at       = now,
        updated_at       = now,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    return {
        "tracking_id":  tracking_id,
        "status":       "RECEIVED",
        "message":      "Claim received — envelope validation queued",
        "portal_url":   f"{_VYNE_PORTAL_URL}/claims/{tracking_id}",
        "submitted_at": now.isoformat(),
    }


@app.get("/v1/claims")
def list_claims(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(VyneClaim).order_by(VyneClaim.created_at.desc())
    if status:
        q = q.filter(VyneClaim.status == status.upper())
    return [_claim_summary(c) for c in q.all()]


@app.get("/v1/claims/{tracking_id}")
def get_claim(tracking_id: str, db: Session = Depends(get_db)):
    claim = db.query(VyneClaim).filter_by(tracking_id=tracking_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _claim_detail(claim)


@app.post("/v1/claims/{tracking_id}/advance")
def advance_claim(tracking_id: str, db: Session = Depends(get_db)):
    """Force the next transmission step now instead of waiting (demo control)."""
    claim = db.query(VyneClaim).filter_by(tracking_id=tracking_id).first()
    if not claim:
        raise HTTPException(404, "Claim not found")
    if claim.status in _TERMINAL:
        return {"message": f"Claim already in terminal status: {claim.status}",
                "status": claim.status}
    _advance_status(claim, db)
    return {"tracking_id": tracking_id, "status": claim.status,
            "as400_claim_no": claim.as400_claim_no}


@app.delete("/v1/claims/reset")
def reset_claims(db: Session = Depends(get_db)):
    deleted = db.query(VyneClaim).delete()
    db.commit()
    return {"deleted": deleted, "message": "All claims cleared"}


@app.get("/v1/stats")
def get_stats(db: Session = Depends(get_db)):
    all_claims = db.query(VyneClaim).all()
    by_status: dict[str, int] = {}
    total_billed = 0.0
    cob_count = 0
    for c in all_claims:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        total_billed += c.billed_amount or 0.0
        if c.is_cob:
            cob_count += 1

    forwarded = by_status.get("FORWARDED", 0)
    rejected  = by_status.get("REJECTED", 0)
    processed = forwarded + rejected

    return {
        "total_claims":  len(all_claims),
        "by_status":     by_status,
        "total_billed":  round(total_billed, 2),
        "forwarded":     forwarded,
        "rejected":      rejected,
        "in_transit":    len(all_claims) - processed,
        "cob_claims":    cob_count,
        "accept_pct":    round(forwarded / processed * 100, 1) if processed else 0.0,
    }


# ── Serializers ───────────────────────────────────────────────────────────────

def _claim_summary(c: VyneClaim) -> dict:
    return {
        "tracking_id":     c.tracking_id,
        "status":          c.status,
        "subscriber_id":   c.subscriber_id,
        "subscriber_name": c.subscriber_name,
        "patient_name":    c.patient_name,
        "payer_name":      c.payer_name,
        "primary_payer":   c.primary_payer,
        "is_cob":          bool(c.is_cob),
        "billed_amount":   c.billed_amount,
        "procedure_date":  c.procedure_date,
        "cdt_codes":       json.loads(c.cdt_codes or "[]"),
        "filename":        c.filename,
        "as400_claim_no":  c.as400_claim_no,
        "as400_screen_url": c.as400_screen_url,
        "created_at":      c.created_at.isoformat() if c.created_at else None,
        "updated_at":      c.updated_at.isoformat() if c.updated_at else None,
    }


def _claim_detail(c: VyneClaim) -> dict:
    return {
        **_claim_summary(c),
        "payer_id":         c.payer_id,
        "provider_npi":     c.provider_npi,
        "provider_name":    c.provider_name,
        "submission_date":  c.submission_date,
        "response_code":    c.response_code,
        "response_message": c.response_message,
        "envelope_errors":  json.loads(c.envelope_errors or "[]"),
        "forwarded_at":     c.forwarded_at.isoformat() if c.forwarded_at else None,
        "procedures":       json.loads(c.procedures or "[]"),
        "raw_edi":          (c.raw_edi or "")[:4000],
        "patient_details":  json.loads(c.patient_details) if c.patient_details else None,
    }
