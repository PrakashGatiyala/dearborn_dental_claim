"""
HCSC DENTAL CLAIMS — AS/400 adjudication system (mock)

Backend : http://localhost:8002
Green screen : http://localhost:5175

Position in the chain:

    vyne_sender.py  ──►  VYNE GATEWAY (:8001)      clearinghouse — receives and
                             │                      forwards, does not adjudicate
                             ▼
                         AS/400 (:8002)            the payer's legacy adjudicator
                             │                      runs the edit sequence
                 ┌───────────┴───────────┐
                 ▼                       ▼
            PAID (SIMPLE_COB)       SUSP (CROSS_PLAN_COB)
            edits cleared           EDIT 0640 failed
                                         │
                                         ▼
                                  DEARBORN (:8000)  AI agent works the suspense
                                                     and returns a recommendation

Every claim arriving here is a COB claim. The split is whether the two plans'
settlement rules reconcile arithmetically (they do → PAID) or not (→ SUSP).
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from adjudicator import adjudicate_cob, human_review_worksheet, parse_cob_edi
from database import As400Claim, SessionLocal, create_tables, get_db
from payer_data import cob_reference_context, verify_reference_data

# ── Config ────────────────────────────────────────────────────────────────────

_DEARBORN_API_URL    = os.getenv("DEARBORN_API_URL",    "http://localhost:8000")
_DEARBORN_PORTAL_URL = os.getenv("DEARBORN_PORTAL_URL", "http://localhost:5173")
_AS400_PORTAL_URL    = os.getenv("AS400_PORTAL_URL",    "http://localhost:5175")
_VYNE_PORTAL_URL     = os.getenv("VYNE_PORTAL_URL",     "http://localhost:5174")

# Seconds a claim sits in RCVD before the nightly-batch simulation picks it up.
_ADJUDICATION_DELAY = int(os.getenv("AS400_ADJUDICATION_DELAY", "12"))

SYSTEM_NAME = "HCSCDEN01"
LIBRARY     = "CLAIMLIB"

STATUS_TEXT = {
    "RCVD": "RECEIVED - QUEUED FOR ADJUDICATION",
    "ADJU": "ADJUDICATION IN PROGRESS",
    "PAID": "ADJUDICATED - PAYMENT AUTHORISED",
    "SUSP": "SUSPENDED - MANUAL REVIEW REQUIRED",
    "RFRD": "REFERRED TO CLAIMS ANALYST WORKBENCH",
    "RVWD": "REVIEW COMPLETE - RELEASED BY OPERATOR",
    "RJCT": "REJECTED",
}


# ── Startup ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    ref = verify_reference_data()
    print(f"✅ AS/400 claims file ready  —  SYSTEM {SYSTEM_NAME}  LIB {LIBRARY}")
    if ref.get("ok"):
        print(f"   Payer reference data: {ref['members']} members, "
              f"{ref['plans']} plans, {ref['fee_schedules']} fee rows")
    else:
        print(f"   ⚠ Payer reference data not ready: {ref.get('hint') or ref.get('error')}")
    threading.Thread(target=_batch_loop, daemon=True).start()
    yield


app = FastAPI(title="HCSC AS/400 Claims Adjudication (mock)", version="1.0.0", lifespan=lifespan)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5175,http://127.0.0.1:5175,https://magnificent-jalebi-1a0a46.netlify.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip().rstrip("/") for o in _raw_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Claim numbering ───────────────────────────────────────────────────────────

_seq_lock = threading.Lock()


def _next_claim_no(db: Session) -> str:
    with _seq_lock:
        last = db.query(As400Claim).order_by(As400Claim.id.desc()).first()
        n = (last.id if last else 0) + 1
        return f"CLM{n:07d}"


def _batch_no() -> str:
    return "B" + datetime.now().strftime("%y%j")   # julian batch, very AS/400


# ── Referral to the agent workbench ───────────────────────────────────────────

def _refer_to_dearborn(claim: As400Claim) -> tuple[bool, str]:
    """POST the raw EDI to the Dearborn agent system and record the link back."""
    if not claim.raw_edi:
        return False, "NO RAW EDI ON FILE"
    try:
        resp = requests.post(
            f"{_DEARBORN_API_URL}/upload/edi",
            files={"edi_file": (claim.filename or f"{claim.claim_no}.edi",
                               claim.raw_edi.encode(), "text/plain")},
            # Hand over the whole chain so the reviewer at the workbench can
            # trace the claim back through this system and the gateway.
            data={
                "vyne_tracking_id": claim.vyne_id or "",
                "vyne_portal_url":  f"{_VYNE_PORTAL_URL}/claims/{claim.vyne_id}" if claim.vyne_id else "",
                "as400_claim_no":   claim.claim_no,
                "as400_screen_url": f"{_AS400_PORTAL_URL}/claim/{claim.claim_no}",
                "as400_batch_no":   claim.batch_no or "",
                "suspend_code":     claim.suspend_code or "",
                "suspend_reason":   claim.reason_text or "",
            },
            timeout=20,
        )
    except Exception as exc:                      # noqa: BLE001 - surfaced on screen
        return False, f"TRANSMIT FAILED: {exc}"

    if not resp.ok:
        return False, f"HTTP {resp.status_code}"

    data = resp.json()
    claim.dearborn_claim_id   = data.get("claim_id")
    claim.dearborn_portal_url = f"{_DEARBORN_PORTAL_URL}/claim/{data.get('claim_id')}"
    claim.referred_at         = datetime.now(timezone.utc)
    claim.status              = "RFRD"
    return True, claim.dearborn_claim_id or ""


# ── Batch adjudication (background) ───────────────────────────────────────────

def _run_edits(claim: As400Claim, db: Session) -> None:
    parsed = parse_cob_edi(claim.raw_edi or "")
    payer_ctx = cob_reference_context(
        parsed.get("subscriber_id") or "",
        parsed.get("cdt_codes") or [],
    )
    decision = adjudicate_cob(parsed, payer_ctx=payer_ctx)

    claim.primary_payer         = parsed.get("primary_payer")
    claim.primary_payer_id      = parsed.get("primary_payer_id")
    claim.primary_eob_ref       = parsed.get("primary_eob_ref")
    claim.primary_paid          = parsed.get("primary_paid")
    claim.primary_allowed       = parsed.get("primary_allowed")
    claim.primary_settlement    = parsed.get("primary_settlement")
    claim.secondary_settlement  = parsed.get("secondary_settlement")
    claim.secondary_coinsurance = parsed.get("secondary_coinsurance")
    claim.monthly_cap           = parsed.get("monthly_cap")
    claim.term_months           = parsed.get("term_months")

    claim.cob_case_type    = decision["cob_case_type"]
    claim.remaining_amount = decision.get("remaining_amount")
    claim.allowed_amount   = decision.get("allowed_amount")
    claim.paid_amount      = decision.get("paid_amount")
    claim.patient_resp     = decision.get("patient_resp")
    claim.reason_code      = decision.get("reason_code")
    claim.reason_text      = decision.get("reason_text")
    claim.suspend_code     = decision.get("suspend_code")
    claim.edit_trace       = json.dumps(decision.get("edit_trace", []))
    claim.status           = decision["status"]
    claim.updated_at       = datetime.now(timezone.utc)

    print(f"[AS/400] {claim.claim_no} → {claim.status} "
          f"({claim.cob_case_type}{' ' + claim.suspend_code if claim.suspend_code else ''})")

    if claim.status == "SUSP":
        ok, info = _refer_to_dearborn(claim)
        print(f"[AS/400→DEARBORN] {claim.claim_no} "
              f"{'→ ' + info if ok else 'referral failed: ' + info}")

    db.commit()


def _batch_loop() -> None:
    while True:
        time.sleep(5)
        db = SessionLocal()
        try:
            queued = db.query(As400Claim).filter(As400Claim.status == "RCVD").all()
            now = datetime.now(timezone.utc)
            for claim in queued:
                created = (claim.created_at or now)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now - created).total_seconds() >= _ADJUDICATION_DELAY:
                    _run_edits(claim, db)
        except Exception as exc:                  # noqa: BLE001
            print(f"[AS/400 batch] error: {exc}")
        finally:
            db.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/as400/health")
def health():
    ref = verify_reference_data()
    return {
        "status": "ok",
        "system": SYSTEM_NAME,
        "library": LIBRARY,
        "database": "postgresql",
        "payer_reference_data": ref,
    }


@app.get("/as400/reference/{subscriber_id}")
def reference_snapshot(subscriber_id: str, cdt: str = ""):
    """Member + plan + fee-schedule totals from public schema (read-only)."""
    codes = [c.strip() for c in cdt.split(",") if c.strip()] if cdt else []
    ctx = cob_reference_context(subscriber_id, codes)
    if not ctx:
        raise HTTPException(404, "MEMBER OR PLAN DATA NOT FOUND")
    return ctx


@app.post("/as400/claims/receive")
async def receive_claim(
    edi_file: UploadFile = File(...),
    vyne_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """Inbound from the Vyne gateway. Writes the claim to the file as RCVD."""
    raw = (await edi_file.read()).decode("utf-8", errors="replace")
    parsed = parse_cob_edi(raw)

    claim_no = _next_claim_no(db)
    now = datetime.now(timezone.utc)

    claim = As400Claim(
        claim_no        = claim_no,
        vyne_id         = vyne_id,
        batch_no        = _batch_no(),
        subscriber_id   = parsed.get("subscriber_id"),
        subscriber_name = parsed.get("subscriber_name"),
        patient_name    = parsed.get("patient_name") or parsed.get("subscriber_name"),
        provider_npi    = parsed.get("provider_npi"),
        provider_name   = parsed.get("provider_name"),
        cdt_codes       = json.dumps(parsed.get("cdt_codes", [])),
        procedures      = json.dumps(parsed.get("procedures", [])),
        procedure_date  = parsed.get("procedure_date"),
        billed_amount   = parsed.get("billed_amount"),
        primary_payer   = parsed.get("primary_payer"),
        primary_paid    = parsed.get("primary_paid"),
        status          = "RCVD",
        reason_code     = "R000",
        reason_text     = STATUS_TEXT["RCVD"],
        raw_edi         = raw[:20000],
        filename        = edi_file.filename,
        created_at      = now,
        updated_at      = now,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    return {
        "claim_no":   claim_no,
        "status":     "RCVD",
        "batch_no":   claim.batch_no,
        "message":    STATUS_TEXT["RCVD"],
        "screen_url": f"{_AS400_PORTAL_URL}/claim/{claim_no}",
    }


@app.get("/as400/claims")
def list_claims(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(As400Claim).order_by(As400Claim.id.desc())
    if status:
        wanted = [s.strip().upper() for s in status.split(",") if s.strip()]
        q = q.filter(As400Claim.status.in_(wanted))
    return [_summary(c) for c in q.all()]


@app.get("/as400/claims/{claim_no}")
def get_claim(claim_no: str, db: Session = Depends(get_db)):
    claim = db.query(As400Claim).filter_by(claim_no=claim_no.upper()).first()
    if not claim:
        raise HTTPException(404, "CLAIM NOT FOUND ON FILE")
    return _detail(claim)


@app.get("/as400/claims/{claim_no}/worksheet")
def get_worksheet(claim_no: str, db: Session = Depends(get_db)):
    """The manual-review instruction sheet printed for a suspended claim."""
    claim = db.query(As400Claim).filter_by(claim_no=claim_no.upper()).first()
    if not claim:
        raise HTTPException(404, "CLAIM NOT FOUND ON FILE")
    if claim.status not in ("SUSP", "RFRD", "RVWD"):
        raise HTTPException(400, f"CLAIM NOT IN SUSPENSE (STATUS {claim.status})")

    parsed = parse_cob_edi(claim.raw_edi or "")
    payer_ctx = cob_reference_context(
        parsed.get("subscriber_id") or "",
        parsed.get("cdt_codes") or [],
    )
    decision = adjudicate_cob(parsed, payer_ctx=payer_ctx)
    return {
        "claim_no": claim.claim_no,
        "suspend_code": claim.suspend_code,
        "suspend_text": claim.reason_text,
        **human_review_worksheet(parsed, decision),
    }


@app.post("/as400/claims/{claim_no}/adjudicate")
def force_adjudicate(claim_no: str, db: Session = Depends(get_db)):
    """Operator forces the edit sequence now instead of waiting for the batch."""
    claim = db.query(As400Claim).filter_by(claim_no=claim_no.upper()).first()
    if not claim:
        raise HTTPException(404, "CLAIM NOT FOUND ON FILE")
    if claim.status not in ("RCVD", "ADJU"):
        return {"claim_no": claim.claim_no, "status": claim.status,
                "message": f"ALREADY ADJUDICATED - STATUS {claim.status}"}
    _run_edits(claim, db)
    return {"claim_no": claim.claim_no, "status": claim.status,
            "suspend_code": claim.suspend_code, "message": STATUS_TEXT.get(claim.status, "")}


@app.post("/as400/claims/{claim_no}/refer")
def refer(claim_no: str, db: Session = Depends(get_db)):
    """Re-send a suspended claim to the Dearborn agent workbench."""
    claim = db.query(As400Claim).filter_by(claim_no=claim_no.upper()).first()
    if not claim:
        raise HTTPException(404, "CLAIM NOT FOUND ON FILE")
    if claim.status not in ("SUSP", "RFRD"):
        raise HTTPException(400, f"CLAIM NOT IN SUSPENSE (STATUS {claim.status})")

    ok, info = _refer_to_dearborn(claim)
    db.commit()
    if not ok:
        raise HTTPException(502, f"REFERRAL FAILED - {info}")
    return {
        "claim_no": claim.claim_no,
        "status": claim.status,
        "dearborn_claim_id": claim.dearborn_claim_id,
        "dearborn_portal_url": claim.dearborn_portal_url,
    }


@app.post("/as400/claims/{claim_no}/pay")
def pay(
    claim_no: str,
    operator: str = Form(default="WORKBENCH"),
    approved_amount: float = Form(...),
    dearborn_claim_id: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """Workbench write-back: a technician approved the coordinated payment."""
    claim = db.query(As400Claim).filter_by(claim_no=claim_no.upper()).first()
    if not claim:
        raise HTTPException(404, "CLAIM NOT FOUND ON FILE")
    if claim.status == "PAID":
        return {"claim_no": claim.claim_no, "status": "PAID", "paid_amount": claim.paid_amount}
    if claim.status not in ("SUSP", "RFRD", "RVWD"):
        raise HTTPException(400, f"CLAIM NOT IN SUSPENSE (STATUS {claim.status})")

    claim.status      = "PAID"
    claim.paid_amount = approved_amount
    claim.operator_id = operator
    claim.reason_text = (f"PAID - COB COORDINATED, APPROVED IN WORKBENCH"
                         f"{' ' + dearborn_claim_id if dearborn_claim_id else ''}")
    claim.updated_at  = datetime.now(timezone.utc)
    db.commit()
    print(f"[AS/400] {claim.claim_no} → PAID ${approved_amount:,.2f} (workbench approval)")
    return {"claim_no": claim.claim_no, "status": "PAID", "paid_amount": approved_amount}


@app.post("/as400/claims/{claim_no}/release")
def release(claim_no: str, operator: str = Form(default="OPER01"), db: Session = Depends(get_db)):
    """Operator releases a reviewed claim back into the paid file."""
    claim = db.query(As400Claim).filter_by(claim_no=claim_no.upper()).first()
    if not claim:
        raise HTTPException(404, "CLAIM NOT FOUND ON FILE")
    if claim.status not in ("SUSP", "RFRD"):
        raise HTTPException(400, f"CLAIM NOT IN SUSPENSE (STATUS {claim.status})")

    claim.status      = "RVWD"
    claim.operator_id = operator
    claim.reason_text = STATUS_TEXT["RVWD"]
    claim.updated_at  = datetime.now(timezone.utc)
    db.commit()
    return {"claim_no": claim.claim_no, "status": claim.status, "operator": operator}


@app.delete("/as400/claims/reset")
def reset(db: Session = Depends(get_db)):
    deleted = db.query(As400Claim).delete()
    db.commit()
    return {"deleted": deleted, "message": "CLAIM FILE CLEARED"}


@app.get("/as400/stats")
def stats(db: Session = Depends(get_db)):
    claims = db.query(As400Claim).all()
    by_status: dict[str, int] = {}
    billed = paid = 0.0
    for c in claims:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        billed += c.billed_amount or 0.0
        paid   += c.paid_amount or 0.0

    auto     = by_status.get("PAID", 0)
    suspense = by_status.get("SUSP", 0) + by_status.get("RFRD", 0) + by_status.get("RVWD", 0)
    worked   = auto + suspense
    return {
        "system":          SYSTEM_NAME,
        "library":         LIBRARY,
        "batch_no":        _batch_no(),
        "total_claims":    len(claims),
        "by_status":       by_status,
        "auto_adjudicated": auto,
        "suspense":        suspense,
        "auto_pct":        round(auto / worked * 100, 1) if worked else 0.0,
        "total_billed":    round(billed, 2),
        "total_paid":      round(paid, 2),
    }


# ── Serializers ───────────────────────────────────────────────────────────────

def _summary(c: As400Claim) -> dict:
    return {
        "claim_no":       c.claim_no,
        "vyne_id":        c.vyne_id,
        "batch_no":       c.batch_no,
        "status":         c.status,
        "status_text":    STATUS_TEXT.get(c.status, ""),
        "cob_case_type":  c.cob_case_type,
        "suspend_code":   c.suspend_code,
        "reason_code":    c.reason_code,
        "patient_name":   c.patient_name,
        "subscriber_id":  c.subscriber_id,
        "primary_payer":  c.primary_payer,
        "billed_amount":  c.billed_amount,
        "primary_paid":   c.primary_paid,
        "paid_amount":    c.paid_amount,
        "procedure_date": c.procedure_date,
        "cdt_codes":      json.loads(c.cdt_codes or "[]"),
        "dearborn_claim_id":   c.dearborn_claim_id,
        "dearborn_portal_url": c.dearborn_portal_url,
        "created_at":     c.created_at.isoformat() if c.created_at else None,
        "updated_at":     c.updated_at.isoformat() if c.updated_at else None,
    }


def _detail(c: As400Claim) -> dict:
    return {
        **_summary(c),
        "subscriber_name":      c.subscriber_name,
        "provider_name":        c.provider_name,
        "provider_npi":         c.provider_npi,
        "procedures":           json.loads(c.procedures or "[]"),
        "primary_payer_id":     c.primary_payer_id,
        "primary_eob_ref":      c.primary_eob_ref,
        "primary_allowed":      c.primary_allowed,
        "primary_settlement":   c.primary_settlement,
        "secondary_settlement": c.secondary_settlement,
        "secondary_coinsurance": c.secondary_coinsurance,
        "monthly_cap":          c.monthly_cap,
        "term_months":          c.term_months,
        "remaining_amount":     c.remaining_amount,
        "allowed_amount":       c.allowed_amount,
        "patient_resp":         c.patient_resp,
        "reason_text":          c.reason_text,
        "edit_trace":           json.loads(c.edit_trace or "[]"),
        "operator_id":          c.operator_id,
        "referred_at":          c.referred_at.isoformat() if c.referred_at else None,
        "filename":             c.filename,
        "raw_edi":              (c.raw_edi or "")[:4000],
    }
