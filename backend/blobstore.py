"""
Postgres-backed replacement for the old storage/ folder.

Every file the medallion pipeline used to write to disk (bronze EDI/PDF, silver
extraction, gold structured.json, meta.json) is now a row in `claim_files`.
Nothing is written to the filesystem.
"""
from __future__ import annotations

import json

from database import ClaimFile, SessionLocal


def marker(layer: str, claim_id: str) -> str:
    """Value kept in claims.bronze_path / silver_path / gold_path.

    Those columns used to hold a folder path; code only tests them for truthiness,
    so a db:// marker keeps that working without touching disk.
    """
    return f"db://{layer}/{claim_id}"


def put(claim_id: str, layer: str, name: str, data: bytes | str) -> None:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    db = SessionLocal()
    try:
        row = db.query(ClaimFile).filter_by(claim_id=claim_id, layer=layer, name=name).first()
        if row:
            row.content = raw
        else:
            db.add(ClaimFile(claim_id=claim_id, layer=layer, name=name, content=raw))
        db.commit()
    finally:
        db.close()


def put_json(claim_id: str, layer: str, name: str, obj) -> None:
    put(claim_id, layer, name, json.dumps(obj, indent=2))


def get_bytes(claim_id: str, layer: str, name: str) -> bytes | None:
    db = SessionLocal()
    try:
        row = db.query(ClaimFile).filter_by(claim_id=claim_id, layer=layer, name=name).first()
        return bytes(row.content) if row else None
    finally:
        db.close()


def get_text(claim_id: str, layer: str, name: str) -> str | None:
    raw = get_bytes(claim_id, layer, name)
    return raw.decode("utf-8", errors="replace") if raw is not None else None


def get_json(claim_id: str, layer: str, name: str):
    text = get_text(claim_id, layer, name)
    return json.loads(text) if text else None


def delete_all() -> int:
    db = SessionLocal()
    try:
        n = db.query(ClaimFile).delete()
        db.commit()
        return n
    finally:
        db.close()
