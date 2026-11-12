"""
COB claim sender — transmits 837D Coordination of Benefits claims into the chain.

    vyne_sender.py  ──►  VYNE (:8001)  ──►  AS/400 (:8002)  ──►  DEARBORN (:8000)
                         clearinghouse      adjudicates          agent workbench
                                            the COB claims       for suspended ones

Every file in the dataset is a COB claim. The AS/400 clears the ones whose two
plans settle the same way, and suspends the ones whose settlement rules are
incompatible — those are the claims that reach the agent workbench.

Generate the dataset first:
    python cob_edi_generator.py --count 12

Usage:
    python vyne_sender.py                 # send one file, then wait between each
    python vyne_sender.py --once          # send one file and exit
    python vyne_sender.py --interval 30   # custom interval in seconds
    python vyne_sender.py --all           # send everything with no waiting

Delete vyne_sent_log.json to reset and re-send all files.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT         = Path(__file__).parent
DATASET_DIR  = Path(os.getenv("COB_DATASET_DIR", ROOT / "datasets" / "cob_edi"))
VYNE_API     = os.getenv("VYNE_API_URL", "http://localhost:8001")
API_ENDPOINT = f"{VYNE_API}/v1/claims/submit"
SENT_LOG     = ROOT / "vyne_sent_log.json"
INTERVAL_SEC = 45

VYNE_PORTAL  = os.getenv("VYNE_PORTAL_URL",  "http://localhost:5174")
AS400_PORTAL = os.getenv("AS400_PORTAL_URL", "http://localhost:5175")
AGENT_PORTAL = os.getenv("DEARBORN_PORTAL_URL", "http://localhost:5173")


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def load_sent() -> set[str]:
    if SENT_LOG.exists():
        return set(json.loads(SENT_LOG.read_text()))
    return set()


def save_sent(sent: set[str]):
    SENT_LOG.write_text(json.dumps(sorted(sent), indent=2))


def pending(sent: set[str]) -> list[Path]:
    return [f for f in sorted(DATASET_DIR.glob("*.edi")) if f.name not in sent]


def load_details() -> dict[str, dict]:
    """Supporting documents per file, from the generator's manifest."""
    manifest = DATASET_DIR / "manifest.json"
    if not manifest.exists():
        return {}
    try:
        return {r["filename"]: r["details"] for r in json.loads(manifest.read_text())
                if r.get("details")}
    except (ValueError, KeyError):
        return {}


def send(path: Path, details: dict | None = None) -> dict | None:
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                API_ENDPOINT,
                files={"edi_file": (path.name, f, "text/plain")},
                data={"details": json.dumps(details)} if details else None,
                timeout=30,
            )
        if resp.ok:
            return resp.json()
        log(f"  FAIL  Server returned {resp.status_code}: {resp.text[:200]}")
        return None
    except requests.ConnectionError:
        log(f"  FAIL  Cannot connect to {API_ENDPOINT} — is the Vyne gateway running?")
        log(r"         Start it with: cd vyne_mock\backend && uvicorn main:app --port 8001")
        return None
    except Exception as exc:
        log(f"  FAIL  {exc}")
        return None


def run(interval: int, once: bool, send_all: bool = False):
    log("=" * 68)
    log("  COB CLAIM SENDER — 837D Coordination of Benefits")
    log(f"  Dataset   : {DATASET_DIR}")
    log(f"  Endpoint  : {API_ENDPOINT}")
    log(f"  Vyne      : {VYNE_PORTAL}   (clearinghouse)")
    log(f"  AS/400    : {AS400_PORTAL}   (adjudication — green screen)")
    log(f"  Workbench : {AGENT_PORTAL}   (suspended claims)")
    log(f"  Interval  : {interval}s  |  Once: {once}  |  All: {send_all}")
    log("=" * 68)

    if not DATASET_DIR.exists():
        log(f"ERROR: Dataset folder not found: {DATASET_DIR}")
        log("       Generate it first:  python cob_edi_generator.py --count 12")
        sys.exit(1)

    sent = load_sent()
    all_details = load_details()

    while True:
        files = pending(sent)
        if not files:
            log("All EDI files have been sent this session.")
            log("Delete vyne_sent_log.json to reset.")
            break

        path = files[0]
        log(f">> Transmitting to Vyne: {path.name}")

        result = send(path, all_details.get(path.name))
        if result:
            tid = result.get("tracking_id", "?")
            log(f"  OK  Vyne Tracking ID : {tid}")
            log(f"      Status           : {result.get('status', '?')}")
            log(f"      View at          : {result.get('portal_url', '')}")
            sent.add(path.name)
            save_sent(sent)
        else:
            log("  FAIL  Will retry on next cycle.")

        if once:
            break

        remaining = pending(sent)
        if not remaining:
            log("All files sent. Exiting.")
            break

        if send_all:
            continue

        log(f"  Next in {interval}s  ({len(remaining)} file(s) remaining) — Ctrl+C to stop")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log("Stopped by user.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="COB 837D claim sender")
    parser.add_argument("--once",     action="store_true", help="Send one file and exit")
    parser.add_argument("--all",      action="store_true", help="Send every file with no waiting")
    parser.add_argument("--interval", type=int, default=INTERVAL_SEC)
    args = parser.parse_args()
    run(interval=args.interval, once=args.once, send_all=args.all)
