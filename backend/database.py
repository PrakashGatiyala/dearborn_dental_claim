import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, DateTime,
    LargeBinary, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dental:dental123@localhost:5432/dental_claims")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres.vocopspeoxwzbmlrbiaq:Ivakrap20112003@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ── Master Insurance Tables ──────────────────────────────────────────────────

class Plan(Base):
    """Insurance plan (PPO Bronze / Silver / Gold)."""
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String, unique=True, nullable=False)   # e.g. PPO-SILVER-TX
    plan_name = Column(String, nullable=False)
    plan_type = Column(String, nullable=False)               # PPO or HMO
    tier = Column(String, nullable=False)                    # Bronze, Silver, Gold
    annual_max = Column(Integer, nullable=False)
    deductible = Column(Integer, nullable=False)
    coinsurance_pct = Column(Float, nullable=False)          # 0.5 = plan pays 50%
    lifetime_ortho_max = Column(Integer, default=0)


class Member(Base):
    """Subscriber / policyholder."""
    __tablename__ = "members"

    id = Column(Integer, primary_key=True)
    subscriber_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    dob = Column(String, nullable=False)                     # YYYY-MM-DD
    plan_id = Column(String, nullable=False)
    enrollment_date = Column(String, nullable=False)         # YYYY-MM-DD
    group_id = Column(String)
    secondary_insurance = Column(String)                     # null if none
    is_active = Column(Boolean, default=True)


class PlanMember(Base):
    """All individuals covered under a policy (subscriber + dependents)."""
    __tablename__ = "plan_members"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String, nullable=False)
    subscriber_id = Column(String, nullable=False)           # head of household
    member_name = Column(String, nullable=False)
    relationship = Column(String, nullable=False)            # subscriber, spouse, child
    dob = Column(String)
    member_id = Column(String, unique=True, nullable=False)  # individual member ID


class CoverageRule(Base):
    """Rules per CDT code prefix per plan."""
    __tablename__ = "coverage_rules"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String, nullable=False)
    cdt_prefix = Column(String, nullable=False)              # first 4 chars: "D274"
    procedure_category = Column(String, nullable=False)
    coverage_pct = Column(Float, nullable=False)
    requires_predetermination = Column(Boolean, default=False)
    requires_xray = Column(Boolean, default=False)
    waiting_period_months = Column(Integer, default=0)
    min_amount_for_predet = Column(Integer, default=0)       # predet required only above this


class FeeSchedule(Base):
    """Contracted fees per CDT code per plan."""
    __tablename__ = "fee_schedules"

    id = Column(Integer, primary_key=True)
    plan_id = Column(String, nullable=False)
    cdt_code = Column(String, nullable=False)                # full code: D2740
    procedure_name = Column(String, nullable=False)
    ucr_fee = Column(Float, nullable=False)                  # usual & customary rate
    ppo_allowed_fee = Column(Float, nullable=False)          # contracted PPO rate


# ── Operational Claim Tracking ────────────────────────────────────────────────

class Claim(Base):
    """Tracks each uploaded claim through the medallion pipeline."""
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True)
    claim_id = Column(String, unique=True, nullable=False)
    status = Column(String, default="UPLOADED")
    # Possible statuses: UPLOADED → SILVER_DONE → GOLD_DONE → ADJUDICATED
    bronze_path = Column(String)
    silver_path = Column(String)
    gold_path = Column(String)
    decision_json = Column(Text)                             # final agent output
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Provenance ───────────────────────────────────────────────────────────
    # Where this claim came from. "UPLOAD" means someone used the form here;
    # "AS400_REFERRAL" means the payer's adjudicator suspended it and handed it
    # over. For a referral we keep the whole chain so the reviewer can trace the
    # claim back through both upstream systems.
    source              = Column(String, default="UPLOAD")
    vyne_tracking_id    = Column(String)   # VYN-12345678
    vyne_portal_url     = Column(String)
    as400_claim_no      = Column(String)   # CLM0000003
    as400_screen_url    = Column(String)
    as400_batch_no      = Column(String)
    suspend_code        = Column(String)   # COB-03
    suspend_reason      = Column(Text)
    referral_received_at = Column(DateTime)

    # Technician outcome, written back to the payer
    resolution          = Column(String)   # APPROVED | HELD
    resolution_amount   = Column(Float)
    resolved_at         = Column(DateTime)


class ClaimFile(Base):
    """
    The medallion layers, stored in Postgres instead of on disk.

    layer is bronze | silver | gold; name is the file it replaces, e.g.
    transmission.edi, meta.json, extracted.json, structured.json, claim.pdf.
    """
    __tablename__ = "claim_files"
    __table_args__ = (UniqueConstraint("claim_id", "layer", "name", name="uq_claim_file"),)

    id = Column(Integer, primary_key=True)
    claim_id = Column(String, nullable=False, index=True)
    layer = Column(String, nullable=False)
    name = Column(String, nullable=False)
    content = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OrthoTreatmentHistory(Base):
    """Tracks orthodontic work-in-progress and age-ambiguity cases."""
    __tablename__ = "ortho_treatment_history"

    id                      = Column(Integer, primary_key=True)
    subscriber_id           = Column(String, nullable=False, index=True)
    patient_name            = Column(String)
    patient_dob             = Column(String)          # YYYY-MM-DD
    treatment_start_date    = Column(String)          # YYYY-MM-DD
    total_treatment_months  = Column(Integer)         # e.g. 24
    months_completed        = Column(Integer)
    prior_plan_id           = Column(String)          # plan that started treatment
    prior_plan_name         = Column(String)
    prior_plan_paid         = Column(Float, default=0.0)
    prior_plan_monthly_rate = Column(Float, default=0.0)
    clinical_narrative      = Column(Text)            # doctor's clinical notes


class EobRecord(Base):
    """EOB from primary plan — used for cross-plan COB calculation."""
    __tablename__ = "eob_records"

    id                  = Column(Integer, primary_key=True)
    subscriber_id       = Column(String, nullable=False, index=True)
    eob_number          = Column(String)
    primary_plan_id     = Column(String)
    primary_plan_name   = Column(String)
    cdt_codes           = Column(Text)                # JSON array
    billed_amount       = Column(Float)
    primary_paid_amount = Column(Float)
    payment_type        = Column(String)              # "lump_sum" or "monthly"
    monthly_amount      = Column(Float)
    months_paid         = Column(Integer)
    claim_date          = Column(String)
    remaining_balance   = Column(Float)


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_tables():
    Base.metadata.create_all(engine)
    _migrate_claims()


def _migrate_claims():
    """
    Add provenance columns to an existing claims table.

    create_all() only creates tables that don't exist — it never alters one that
    does. Without this, an older database keeps the old column set and every
    insert that mentions a new column fails.
    """
    from sqlalchemy import text

    new_cols = [
        ("source",               "VARCHAR"),
        ("vyne_tracking_id",     "VARCHAR"),
        ("vyne_portal_url",      "VARCHAR"),
        ("as400_claim_no",       "VARCHAR"),
        ("as400_screen_url",     "VARCHAR"),
        ("as400_batch_no",       "VARCHAR"),
        ("suspend_code",         "VARCHAR"),
        ("suspend_reason",       "TEXT"),
        ("referral_received_at", "TIMESTAMP"),
        ("resolution",           "VARCHAR"),
        ("resolution_amount",    "FLOAT"),
        ("resolved_at",          "TIMESTAMP"),
    ]

    with engine.connect() as conn:
        for col, col_type in new_cols:
            try:
                conn.execute(text(
                    f"ALTER TABLE claims ADD COLUMN IF NOT EXISTS {col} {col_type}"
                ))
                conn.commit()
            except Exception as exc:                       # noqa: BLE001
                # SQLite and older Postgres lack IF NOT EXISTS on ADD COLUMN.
                if "duplicate" in str(exc).lower() or "already exists" in str(exc).lower():
                    continue
                print(f"[DB migrate] could not add {col}: {exc}")


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
