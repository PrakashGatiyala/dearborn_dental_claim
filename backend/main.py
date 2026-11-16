"""
FastAPI application — 4 endpoints:

  POST /upload                      → run full medallion pipeline, return claim_id + gold data
  GET  /claim/{claim_id}            → return claim status, gold data, and decision if adjudicated
  POST /claim/{claim_id}/adjudicate → run the AI agent, return decision JSON
  GET  /claims                      → list all claims (most recent first)
"""
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env BEFORE importing anything that reads env vars at import time
# (database.py reads DATABASE_URL, agent.py reads AZURE_OPENAI_DEPLOYMENT).
# Under Docker Compose these arrive via env_file; running uvicorn directly,
# nothing would supply them without this.
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)
if not os.getenv("AZURE_OPENAI_API_KEY"):
    load_dotenv()  # fall back to a .env beside the working directory

from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import create_tables, get_db, Claim, ClaimFile
from medallion import (
    process_bronze, process_silver, process_gold,
    process_bronze_edi, process_silver_edi, process_gold_edi,
)
import blobstore
import human_input
from agent import adjudicate
from cobd import determine as cobd_determine
from cob_filing_review import compute_filing_vs_cobd, display_metrics_for_claim
from pydantic import BaseModel


class AdjudicateBody(BaseModel):
    values: dict = {}
    note: str = ""


# ── App startup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry DB table creation — postgres may need a moment even after healthcheck
    for attempt in range(1, 11):
        try:
            create_tables()
            print("✅ Database tables ready")
            break
        except Exception as exc:
            print(f"⏳ DB not ready (attempt {attempt}/10): {exc}")
            time.sleep(3)

    # Say plainly whether the agent can call the model. Without this, a missing
    # key only shows up later as an unexplained NEEDS_REVIEW on a claim.
    if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
        print(f"✅ Azure OpenAI configured — endpoint {os.getenv('AZURE_OPENAI_ENDPOINT')}, "
              f"deployment {os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')}")
    else:
        print("⚠️  Azure OpenAI NOT configured — AZURE_OPENAI_API_KEY / "
              "AZURE_OPENAI_ENDPOINT missing. Adjudication will return "
              "NEEDS_REVIEW without assessing the claim.")
        print(f"    Looked for a .env at: {_ENV_PATH}")

    yield


app = FastAPI(title="Dental Claim Adjudicator", lifespan=lifespan)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
_origins = [o.strip().rstrip("/") for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Cheap liveness check for Render (no database work)."""
    return {"status": "ok", "service": "dearborn-workbench", "deploy_tag": "2026-03-16-test"}


@app.post("/upload")
async def upload_claim(
    claim_pdf: UploadFile = File(...),
    policy_pdf: UploadFile = File(...),
):
    """
    Accept two PDF uploads, run the Bronze → Silver → Gold pipeline,
    and return the claim_id plus the structured gold-layer data.
    """
    claim_bytes = await claim_pdf.read()
    policy_bytes = await policy_pdf.read()

    claim_id = process_bronze(claim_bytes, policy_bytes, claim_pdf.filename)
    process_silver(claim_id)
    gold_data = process_gold(claim_id)

    return {
        "claim_id": claim_id,
        "status": "GOLD_DONE",
        "gold_data": gold_data,
    }


@app.post("/upload/edi")
async def upload_edi(
    edi_file: UploadFile = File(...),
    # Provenance, sent by the AS/400 when it refers a suspended claim. All
    # optional so edi_sender.py and manual posts still work.
    vyne_tracking_id: str | None = Form(default=None),
    vyne_portal_url:  str | None = Form(default=None),
    as400_claim_no:   str | None = Form(default=None),
    as400_screen_url: str | None = Form(default=None),
    as400_batch_no:   str | None = Form(default=None),
    suspend_code:     str | None = Form(default=None),
    suspend_reason:   str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Accept a raw EDI 837D file, run it through the Bronze → Silver → Gold
    medallion pipeline, and return the claim_id plus structured gold data.

    Called by the AS/400 when its edit sequence suspends a COB claim, and by
    edi_sender.py for direct submissions.
    """
    edi_bytes = await edi_file.read()

    claim_id  = process_bronze_edi(edi_bytes, edi_file.filename)
    process_silver_edi(claim_id)
    gold_data = process_gold_edi(claim_id)

    # Record where it came from, so the reviewer can trace the claim back
    # through the AS/400 and the Vyne gateway.
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    if claim:
        referred = bool(as400_claim_no)
        claim.source               = "AS400_REFERRAL" if referred else "UPLOAD"
        claim.vyne_tracking_id     = vyne_tracking_id
        claim.vyne_portal_url      = vyne_portal_url
        claim.as400_claim_no       = as400_claim_no
        claim.as400_screen_url     = as400_screen_url
        claim.as400_batch_no       = as400_batch_no
        claim.suspend_code         = suspend_code
        claim.suspend_reason       = suspend_reason
        claim.referral_received_at = datetime.now(timezone.utc) if referred else None
        db.commit()
        if referred:
            print(f"[Referral] {claim_id} ← AS/400 {as400_claim_no} "
                  f"({suspend_code}) ← Vyne {vyne_tracking_id}")

    return {
        "claim_id":  claim_id,
        "status":    "GOLD_DONE",
        "gold_data": gold_data,
    }


@app.get("/claim/{claim_id}")
def get_claim(claim_id: str, db: Session = Depends(get_db)):
    """Return the current status, gold data, and decision (if adjudicated) for a claim."""
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Load the medallion layers from Postgres (used when revisiting a claim)
    gold_data = blobstore.get_json(claim_id, "gold", "structured.json") if claim.gold_path else None
    bronze_meta = blobstore.get_json(claim_id, "bronze", "meta.json") if claim.bronze_path else None

    # Silver data — handles both PDF and EDI input types
    silver_summary = None
    if claim.silver_path:
        sv = blobstore.get_json(claim_id, "silver", "extracted.json")
        if sv:
            input_type = sv.get("input_type", "pdf")

            if input_type == "edi":
                edi_block = sv.get("edi", {})
                silver_summary = {
                    "extracted_at": sv.get("extracted_at"),
                    "input_type":   "edi",
                    "edi": {
                        "segment_count": edi_block.get("segment_count", 0),
                        "segments":      edi_block.get("segments", []),
                        "raw_preview":   edi_block.get("raw_preview", ""),
                    },
                }
            else:
                silver_summary = {
                    "extracted_at": sv.get("extracted_at"),
                    "input_type":   "pdf",
                    "claim_pdf": {
                        "method":       sv["claim_pdf"]["method"],
                        "page_count":   sv["claim_pdf"]["page_count"],
                        "text_preview": sv["claim_pdf"]["text"][:600],
                    },
                    "policy_pdf": {
                        "method":       sv["policy_pdf"]["method"],
                        "page_count":   sv["policy_pdf"]["page_count"],
                        "text_preview": sv["policy_pdf"]["text"][:600],
                    },
                }

    # What the page shows is the claim as it stands now: technician edits applied.
    original_gold = gold_data
    gold_data = human_input.effective_gold(claim_id, gold_data)
    ov = human_input.get_overrides(claim_id)

    return {
        "claim_id": claim.claim_id,
        "status": claim.status,
        "bronze_meta": bronze_meta,
        "silver_summary": silver_summary,
        "gold_data": gold_data,
        "original_gold": original_gold,
        "overrides": ov,
        "editable_fields": {k: {"label": v[0],
                                "options": list(v[1]) if isinstance(v[1], tuple) else None,
                                "integer": v[1] is int}
                            for k, v in human_input.EDITABLE.items()},
        "documents": human_input.list_documents(claim_id),
        "cobd": (cobd := cobd_determine(gold_data) if gold_data and gold_data.get("cob_flag") else None),
        "filing_vs_cobd": compute_filing_vs_cobd(gold_data, cobd, claim.suspend_code),
        "display_metrics": display_metrics_for_claim(gold_data, cobd, claim.suspend_code),
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "decision": json.loads(claim.decision_json) if claim.decision_json else None,
        "resolution": claim.resolution,
        "resolution_amount": claim.resolution_amount,

        # The chain this claim travelled: practice → Vyne → AS/400 → here
        "provenance": {
            # None means the row predates referral tracking — don't guess that
            # it was an upload, say the origin is unknown.
            "source":            claim.source,
            "vyne_tracking_id":  claim.vyne_tracking_id,
            "vyne_portal_url":   claim.vyne_portal_url,
            "as400_claim_no":    claim.as400_claim_no,
            "as400_screen_url":  claim.as400_screen_url,
            "as400_batch_no":    claim.as400_batch_no,
            "suspend_code":      claim.suspend_code,
            "suspend_reason":    claim.suspend_reason,
            "referred_at":       claim.referral_received_at.isoformat()
                                 if claim.referral_received_at else None,
        },
    }


@app.post("/claim/{claim_id}/adjudicate")
def run_adjudication(claim_id: str, body: AdjudicateBody | None = None,
                     db: Session = Depends(get_db)):
    """
    Run the AI agent against the claim. Can be called any number of times: each run
    uses the current edited values and every document uploaded so far. An optional
    body {values, note} saves technician edits before the run.
    Returns the decision JSON with justification and data sources.
    """
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status not in ("GOLD_DONE", "ADJUDICATED"):
        raise HTTPException(
            status_code=400,
            detail=f"Claim is not ready for adjudication (status: {claim.status})"
        )

    if claim.resolution == "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="This claim was already approved and written back to the AS/400; "
                   "it can't be re-run.")

    gold_data = blobstore.get_json(claim_id, "gold", "structured.json")
    if not gold_data:
        raise HTTPException(status_code=400, detail="Gold data missing for this claim")

    # Edits submitted with this run are saved first, so they persist for later runs.
    if body is not None:
        try:
            human_input.save_overrides(claim_id, body.values, body.note, gold_data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # The agent sees the claim as it stands now: edits applied, documents attached.
    effective = human_input.effective_gold(claim_id, gold_data, for_agent=True)
    decision = adjudicate(claim_id, effective)

    # Record what human input this run took into account, and re-open the claim
    # for a fresh technician decision (a HELD claim can be re-worked).
    docs = human_input.list_documents(claim_id)
    decision["human_inputs"] = {
        "documents": [d["name"] for d in docs],
        "overrides": effective.get("human_overrides", []),
        "note": effective.get("reviewer_note"),
    }
    cobd = cobd_determine(effective) if effective.get("cob_flag") else None
    fv = compute_filing_vs_cobd(effective, cobd, claim.suspend_code)
    if fv:
        decision["filing_vs_cobd"] = fv
    dm = display_metrics_for_claim(effective, cobd, claim.suspend_code)
    if dm:
        decision["display_metrics"] = dm
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    claim.decision_json = json.dumps(decision)
    claim.resolution = None
    claim.resolution_amount = None
    claim.resolved_at = None
    db.commit()
    human_input.mark_considered(claim_id)
    return decision


@app.get("/claim/{claim_id}/documents")
def list_claim_documents(claim_id: str):
    return human_input.list_documents(claim_id)


@app.post("/claim/{claim_id}/documents")
async def upload_claim_documents(claim_id: str, files: list[UploadFile] = File(...),
                                 db: Session = Depends(get_db)):
    if not db.query(Claim).filter_by(claim_id=claim_id).first():
        raise HTTPException(status_code=404, detail="Claim not found")
    if len(human_input.list_documents(claim_id)) + len(files) > human_input.MAX_DOCS:
        raise HTTPException(status_code=400,
                            detail=f"At most {human_input.MAX_DOCS} documents per claim")
    added = []
    for f in files:
        data = await f.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{f.filename} is over 10 MB")
        added.append(human_input.add_document(claim_id, f.filename or "document", data))
    return added


@app.delete("/claim/{claim_id}/documents/{name}")
def delete_claim_document(claim_id: str, name: str):
    human_input.delete_document(claim_id, name)
    return {"deleted": name}


@app.post("/claim/{claim_id}/resolve")
def resolve_claim(claim_id: str, action: str = Form(...), db: Session = Depends(get_db)):
    """
    Technician approves or holds the agent's recommendation. Approval is written
    back to the payer's AS/400, which marks the claim PAID.
    """
    import urllib.parse
    import urllib.request

    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if not claim.decision_json:
        raise HTTPException(status_code=400, detail="Run the agents before resolving")

    decision = json.loads(claim.decision_json)
    amount = float(decision.get("approved_amount") or 0)
    writeback = None

    if action == "approve":
        if decision.get("decision") != "APPROVED":
            raise HTTPException(status_code=400, detail="Agent did not recommend approval")
        if claim.as400_claim_no:
            base = os.getenv("AS400_API_URL", "http://localhost:8002")
            try:
                body = urllib.parse.urlencode({
                    "approved_amount": amount, "dearborn_claim_id": claim_id,
                    "operator": "WORKBENCH",
                }).encode()
                req = urllib.request.Request(
                    f"{base}/as400/claims/{claim.as400_claim_no}/pay", data=body)
                with urllib.request.urlopen(req, timeout=10) as r:
                    writeback = json.loads(r.read())
            except Exception as exc:                           # noqa: BLE001
                raise HTTPException(status_code=502, detail=f"AS/400 write-back failed: {exc}")
        claim.resolution = "APPROVED"
        claim.resolution_amount = amount
    elif action == "hold":
        claim.resolution = "HELD"
    else:
        raise HTTPException(status_code=400, detail="action must be approve or hold")

    claim.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"claim_id": claim_id, "resolution": claim.resolution,
            "amount": amount, "as400": writeback}


@app.get("/claims")
def list_claims(db: Session = Depends(get_db)):
    """Return all claims ordered by most recent first."""
    claims = db.query(Claim).order_by(Claim.created_at.desc()).all()

    # One query for every claim's gold JSON, not one per claim per poll.
    golds = {}
    for row in db.query(ClaimFile).filter_by(layer="gold", name="structured.json").all():
        try:
            golds[row.claim_id] = json.loads(bytes(row.content).decode("utf-8"))
        except Exception:
            golds[row.claim_id] = {}

    def _gold(c):
        return golds.get(c.claim_id, {})

    def _patient(c):
        g = _gold(c)
        return g.get("patient_name") or g.get("subscriber_name")

    # Demo scope: only confirmed COB claims (two plans on the claim) are shown.
    claims = [c for c in claims if _gold(c).get("cob_flag")]

    def _liability(c):
        d = cobd_determine(_gold(c))
        t = d["terminal"]
        return {"category": d["category"], "role": d["hcsc_role"],
                "rule": t.get("rule"), "node": str(t["node"])}

    return [
        {
            "claim_id": c.claim_id,
            "patient_name": _patient(c),
            "liability": _liability(c),
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "decision": json.loads(c.decision_json).get("decision") if c.decision_json else None,
            "source": c.source,
            "as400_claim_no": c.as400_claim_no,
            "suspend_code": c.suspend_code,
            "resolution": c.resolution,
        }
        for c in claims
    ]
