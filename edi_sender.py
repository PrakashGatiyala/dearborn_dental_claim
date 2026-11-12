"""
EDI Sender — simulates a practice management system transmitting 837D claims.

Usage:
    python edi_sender.py              # send one EDI file now, then wait 5 min between each
    python edi_sender.py --once       # send one file and exit (for manual demos)
    python edi_sender.py --interval 30  # custom interval in seconds

In a client demo: run this in one terminal ("provider system sending claims")
while showing the browser on another screen ("payer platform receiving them").

EDI files are read from the DATASET_DIR folder in rotation.
Sent files are tracked in sent_log.json so each file is sent only once per session.
Delete sent_log.json to reset and re-send all files.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Configuration ─────────────────────────────────────────────────────────────

DATASET_DIR  = Path(r"C:\Users\ParkaviVetrivel\Downloads\Synthetic_Dental_Claim_PDF_EDI_Dataset")
API_ENDPOINT = "http://localhost:8000/upload/edi"
SENT_LOG     = Path(__file__).parent / "sent_log.json"
INTERVAL_SEC = 300   # 5 minutes default


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def load_sent_log() -> set[str]:
    if SENT_LOG.exists():
        return set(json.loads(SENT_LOG.read_text()))
    return set()


def save_sent_log(sent: set[str]):
    SENT_LOG.write_text(json.dumps(sorted(sent), indent=2))


def get_pending_files(sent: set[str]) -> list[Path]:
    """Return EDI files not yet sent this session, sorted by name."""
    all_files = sorted(DATASET_DIR.glob("*.edi"))
    return [f for f in all_files if f.name not in sent]


def send_edi(path: Path) -> dict | None:
    """POST the EDI file to the backend. Returns JSON response or None on error."""
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                API_ENDPOINT,
                files={"edi_file": (path.name, f, "text/plain")},
                timeout=60,
            )
        if resp.ok:
            return resp.json()
        else:
            log(f"  FAIL Server returned {resp.status_code}: {resp.text[:200]}")
            return None
    except requests.ConnectionError:
        log(f"  FAIL Cannot connect to {API_ENDPOINT} -- is the backend running?")
        return None
    except Exception as exc:
        log(f"  FAIL Unexpected error: {exc}")
        return None


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(interval: int, once: bool):
    log("=" * 60)
    log("  EDI SENDER - Dearborn / HCSC Demo")
    log(f"  Dataset : {DATASET_DIR}")
    log(f"  Endpoint: {API_ENDPOINT}")
    log(f"  Interval: {interval}s  |  Once: {once}")
    log("=" * 60)

    if not DATASET_DIR.exists():
        log(f"ERROR: Dataset folder not found: {DATASET_DIR}")
        sys.exit(1)

    sent = load_sent_log()

    while True:
        pending = get_pending_files(sent)

        if not pending:
            log("All EDI files have been sent this session.")
            log("Delete sent_log.json to reset and re-send from the beginning.")
            break

        file_to_send = pending[0]
        log(f">> Sending: {file_to_send.name}")

        result = send_edi(file_to_send)
        if result:
            claim_id = result.get("claim_id", "unknown")
            codes    = result.get("gold_data", {}).get("cdt_codes", [])
            sub      = result.get("gold_data", {}).get("subscriber_id", "")
            billed   = result.get("gold_data", {}).get("billed_amount", 0)
            log(f"  OK  Received as {claim_id}")
            log(f"    Subscriber : {sub}")
            log(f"    CDT codes  : {', '.join(codes)}")
            log(f"    Billed     : ${billed:,.2f}")
            log(f"    View at    : http://localhost:5173/claim/{claim_id}")
            sent.add(file_to_send.name)
            save_sent_log(sent)
        else:
            log(f"  FAIL  Failed -- will retry on next cycle")

        if once:
            break

        remaining = get_pending_files(sent)
        if not remaining:
            log("All files sent. Exiting.")
            break

        log(f"  Next send in {interval}s  ({len(remaining)} file(s) remaining) — Ctrl+C to stop")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log("Stopped by user.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EDI 837D claim sender for demo")
    parser.add_argument("--once",     action="store_true", help="Send one file and exit")
    parser.add_argument("--interval", type=int, default=INTERVAL_SEC, help="Seconds between sends")
    args = parser.parse_args()

    run(interval=args.interval, once=args.once)
