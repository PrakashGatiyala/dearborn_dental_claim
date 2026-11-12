"""
Reset all claim data for a fresh test run.

What this does:
  - Deletes all rows from the 'claims' table (operational data only)
  - Deletes all rows from 'claim_files' (the bronze / silver / gold layers)
  - Keeps all master insurance data intact (plans, members, coverage_rules, fee_schedules)

Run:
  python clear_data.py
"""
from database import SessionLocal, Claim, ClaimFile


def clear():
    db = SessionLocal()
    try:
        claims = db.query(Claim).delete()
        files = db.query(ClaimFile).delete()
        db.commit()
    finally:
        db.close()

    print(f"Deleted {claims} claim(s) and {files} stored file(s) from Postgres.")
    print("Master insurance data (plans, members, rules, fees) is untouched.")
    print("You can now upload fresh claims.")


if __name__ == "__main__":
    clear()
