"""
Human input to a claim after the agent has run: uploaded documents and edited values.

Both are stored in Postgres (claim_files) and folded into the claim the agent sees
on every run, so a technician can add evidence or correct a figure and re-run the
adjudication as many times as they like.

    uploads/<filename>             the document bytes
    uploads/<filename>.meta.json   name, size, extracted text, considered flag
    overrides/current.json         the edited values and reviewer note
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import blobstore
from database import ClaimFile, SessionLocal

TEXT_EXT = (".txt", ".md", ".csv", ".json", ".edi", ".xml", ".log")
MAX_TEXT = 12000          # characters of extracted text kept per document
MAX_DOCS = 20

# field -> (label, kind). These are the values that decide a COB outcome.
EDITABLE = {
    "billed_amount":          ("Billed amount ($)", float),
    "primary_paid_amount":    ("Primary plan paid ($)", float),
    "primary_allowed_amount": ("Primary allowed ($)", float),
    "secondary_coinsurance":  ("HCSC coinsurance (%)", int),
    "secondary_settlement":   ("HCSC settlement", ("LUMP_SUM", "MONTHLY")),
    "monthly_cap":            ("Monthly cap ($)", float),
    "term_months":            ("Term (months)", int),
    # The technician's own figure for what the secondary plan should pay.
    "secondary_owes_override": ("Secondary owes ($)", float),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Documents ─────────────────────────────────────────────────────────────────

def _extract_text(name: str, data: bytes) -> tuple[str, bool]:
    lower = name.lower()
    if lower.endswith(TEXT_EXT):
        return data.decode("utf-8", errors="replace")[:MAX_TEXT], True
    if lower.endswith(".pdf"):
        from extract_text import extract_pdf_to_string
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            tmp.write(data)
            tmp.close()
            text, _method = extract_pdf_to_string(tmp.name)
            return (text or "")[:MAX_TEXT], bool((text or "").strip())
        except Exception:                                  # noqa: BLE001
            return "", False
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    return "", False          # images, Word files etc. are kept but not read


def add_document(claim_id: str, name: str, data: bytes) -> dict:
    name = os.path.basename(name) or "document"
    text, extracted = _extract_text(name, data)
    meta = {"name": name, "size": len(data), "uploaded_at": _now(),
            "extracted": extracted, "text": text, "considered": False}
    blobstore.put(claim_id, "uploads", name, data)
    blobstore.put_json(claim_id, "uploads", f"{name}.meta.json", meta)
    return {k: v for k, v in meta.items() if k != "text"}


def list_documents(claim_id: str, with_text: bool = False) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (db.query(ClaimFile.name)
                  .filter(ClaimFile.claim_id == claim_id, ClaimFile.layer == "uploads",
                          ClaimFile.name.like("%.meta.json")).all())
    finally:
        db.close()
    docs = []
    for (n,) in rows:
        meta = blobstore.get_json(claim_id, "uploads", n)
        if meta:
            docs.append(meta if with_text else {k: v for k, v in meta.items() if k != "text"})
    return sorted(docs, key=lambda d: d.get("uploaded_at", ""))


def delete_document(claim_id: str, name: str) -> None:
    db = SessionLocal()
    try:
        db.query(ClaimFile).filter(
            ClaimFile.claim_id == claim_id, ClaimFile.layer == "uploads",
            ClaimFile.name.in_([name, f"{name}.meta.json"])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def mark_considered(claim_id: str) -> None:
    for d in list_documents(claim_id, with_text=True):
        if not d.get("considered"):
            d["considered"] = True
            blobstore.put_json(claim_id, "uploads", f"{d['name']}.meta.json", d)


# ── Edited values ─────────────────────────────────────────────────────────────

def get_overrides(claim_id: str) -> dict:
    return blobstore.get_json(claim_id, "overrides", "current.json") or {"values": {}, "note": ""}


def save_overrides(claim_id: str, values: dict, note: str, gold: dict) -> dict:
    """Validate and store edits. Values equal to the original are dropped."""
    clean: dict = {}
    for field, raw in (values or {}).items():
        if field not in EDITABLE or raw in (None, ""):
            continue
        kind = EDITABLE[field][1]
        try:
            if isinstance(kind, tuple):
                v = str(raw).upper()
                if v not in kind:
                    raise ValueError
            else:
                v = kind(float(raw)) if kind is int else kind(raw)
                if v < 0:
                    raise ValueError
        except (TypeError, ValueError):
            raise ValueError(f"Invalid value for {EDITABLE[field][0]}: {raw!r}")
        if gold.get(field) != v:
            clean[field] = v
    data = {"values": clean, "note": (note or "").strip(), "updated_at": _now()}
    blobstore.put_json(claim_id, "overrides", "current.json", data)
    return data


def effective_gold(claim_id: str, gold: dict | None, for_agent: bool = False) -> dict | None:
    """The claim as it stands now: original gold + edited values (+ documents for the agent)."""
    if not gold:
        return gold
    merged = dict(gold)
    ov = get_overrides(claim_id)
    changes = []
    for field, v in (ov.get("values") or {}).items():
        changes.append({"field": field, "label": EDITABLE[field][0],
                        "original": gold.get(field), "edited": v})
        merged[field] = v
    merged["edited_fields"] = [c["field"] for c in changes]
    if for_agent:
        merged["human_overrides"] = changes
        merged["reviewer_note"] = ov.get("note") or None
        merged["uploaded_documents"] = [
            {"name": d["name"], "uploaded_at": d["uploaded_at"],
             "text": d.get("text") or "(binary file — text could not be extracted)"}
            for d in list_documents(claim_id, with_text=True)
        ]
    return merged
