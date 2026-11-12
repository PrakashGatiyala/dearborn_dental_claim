"""
Claims store for the HCSC AS/400 adjudication system (mock).

Postgres only (Supabase). Tables live in their own `as400` schema inside the
same database the other two systems use, so nothing collides with them.

Set DATABASE_URL in the repo-root .env, e.g. the Supabase connection string.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Column, DateTime, Float, Integer, MetaData, String, Text, create_engine, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# <repo root>/.env — as400/backend/database.py is two levels below it
_here = Path(__file__).resolve()
if len(_here.parents) > 2:          # not the case inside a flat Docker /app layout
    load_dotenv(_here.parents[2] / ".env")

SCHEMA = "as400"

_url = os.getenv("DATABASE_URL", "").strip()
if _url.startswith("postgres://"):                      # some hosts still emit the old scheme
    _url = "postgresql://" + _url[len("postgres://"):]
if not _url.startswith("postgresql"):
    sys.exit(
        "DATABASE_URL is not set (or is not a Postgres URL).\n"
        "Add your Supabase connection string to the repo-root .env:\n"
        "  DATABASE_URL=postgresql://postgres.<ref>:<password>@<host>:6543/postgres"
    )

engine = create_engine(
    _url, pool_pre_ping=True, pool_recycle=240,
    connect_args={"connect_timeout": 10},      # fail fast instead of hanging a request
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# A schema on the metadata (rather than a search_path option) works through
# Supabase's transaction pooler on port 6543, which rejects startup options.
Base = declarative_base(metadata=MetaData(schema=SCHEMA))


class As400Claim(Base):
    """One row per claim in the payer's legacy adjudication file."""

    __tablename__ = "as400_claims"

    id = Column(Integer, primary_key=True, index=True)

    # Legacy-style keys
    claim_no    = Column(String, unique=True, nullable=False, index=True)  # CLM0000123
    vyne_id     = Column(String, index=True)                               # VYN-12345678
    batch_no    = Column(String)

    # Patient / subscriber
    subscriber_id   = Column(String)
    subscriber_name = Column(String)
    patient_name    = Column(String)

    # Provider
    provider_npi  = Column(String)
    provider_name = Column(String)

    # Clinical
    cdt_codes      = Column(Text)    # JSON array
    procedures     = Column(Text)    # JSON array
    procedure_date = Column(String)

    # Money
    billed_amount    = Column(Float)
    primary_allowed  = Column(Float)
    primary_paid     = Column(Float)
    remaining_amount = Column(Float)
    allowed_amount   = Column(Float)
    paid_amount      = Column(Float)
    patient_resp     = Column(Float)

    # COB
    primary_payer        = Column(String)
    primary_payer_id     = Column(String)
    primary_eob_ref      = Column(String)
    primary_settlement   = Column(String)   # LUMP_SUM | MONTHLY
    secondary_settlement = Column(String)   # LUMP_SUM | MONTHLY
    secondary_coinsurance = Column(Integer)
    monthly_cap          = Column(Float)
    term_months          = Column(Integer)
    cob_case_type        = Column(String)   # SIMPLE_COB | CROSS_PLAN_COB | LIABILITY_REVIEW

    # Adjudication
    status         = Column(String, default="RCVD")   # RCVD|ADJU|PAID|SUSP|RVWD|RJCT
    reason_code    = Column(String)
    reason_text    = Column(Text)
    suspend_code   = Column(String)
    edit_trace     = Column(Text)    # JSON array of edit results
    operator_id    = Column(String)

    # Hand-off to the agent system
    dearborn_claim_id   = Column(String)
    dearborn_portal_url = Column(String)
    referred_at         = Column(DateTime)

    raw_edi  = Column(Text)
    filename = Column(String)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


def create_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate() -> None:
    """Non-destructively add any columns missing from a table made by an older version."""
    expected = {c.name: c.type.compile(engine.dialect) for c in As400Claim.__table__.columns}
    with engine.begin() as conn:
        for name, coltype in expected.items():
            conn.execute(text(
                f'ALTER TABLE "{SCHEMA}".as400_claims ADD COLUMN IF NOT EXISTS {name} {coltype}'
            ))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
