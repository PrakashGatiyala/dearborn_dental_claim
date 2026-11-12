"""
reset_demo.py — clears all three systems in the chain so the demo starts clean.

    VYNE (:8001)  →  AS/400 (:8002)  →  DEARBORN (:8000)

Usage:
    python reset_demo.py

Endpoints default to localhost; override with VYNE_API_URL and AS400_API_URL.
The Dearborn claims table is cleared through the backend's own database module,
so no separate DATABASE_URL is needed.

Note this clears *claims*. It leaves the reference data alone — plans, members,
coverage rules, fee schedules and EOB records seeded by seed_cob_claims.py stay
put, so re-sending the same dataset still resolves.
"""
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent

VYNE_API     = os.getenv("VYNE_API_URL",     "http://localhost:8001")
AS400_API    = os.getenv("AS400_API_URL",    "http://localhost:8002")
DEARBORN_API = os.getenv("DEARBORN_API_URL", "http://localhost:8000")


def _drop_log(name: str, label: str) -> None:
    log = ROOT / name
    if log.exists():
        log.unlink()
        print(f"  {label:<15}: cleared")
    else:
        print(f"  {label:<15}: already clean")


def clear_vyne() -> None:
    print("-- Vyne Gateway (clearinghouse) --")
    try:
        r = requests.delete(f"{VYNE_API}/v1/claims/reset", timeout=10)
        print(f"  Claims deleted : {r.json().get('deleted', '?')}")
    except Exception as e:
        print(f"  WARN  Vyne backend not reachable: {e}")
    _drop_log("vyne_sent_log.json", "Sent log")


def clear_as400() -> None:
    print("-- HCSC AS/400 (adjudication) --")
    try:
        r = requests.delete(f"{AS400_API}/as400/claims/reset", timeout=10)
        print(f"  Claims deleted : {r.json().get('deleted', '?')}")
    except Exception as e:
        print(f"  WARN  AS/400 backend not reachable: {e}")


def clear_dearborn() -> None:
    """
    Clear the agent workbench's claim table.

    Uses the backend's own database module so it connects exactly where the
    backend connects — no need to set DATABASE_URL separately.
    """
    print("-- Dearborn Agent Workbench --")
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from sqlalchemy import text

        from database import SessionLocal  # noqa: PLC0415

        db = SessionLocal()
        try:
            count = db.execute(text("DELETE FROM claims")).rowcount
            files = db.execute(text("DELETE FROM claim_files")).rowcount
            db.commit()
            print(f"  DB claims      : {count} rows deleted")
            print(f"  DB claim files : {files} rows deleted")
        finally:
            db.close()
    except Exception as e:
        print(f"  WARN  DB clear failed: {e}")
        print("        Is the backend's database reachable?")
    _drop_log("sent_log.json", "Sent log")


if __name__ == "__main__":
    print("\n== Demo Reset ==\n")
    clear_vyne()
    print()
    clear_as400()
    print()
    clear_dearborn()
    print("\nDone. Run vyne_sender.py to start fresh.\n")
