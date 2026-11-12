"""
Database for the Vyne Dental mock gateway.

Postgres only (Supabase). Tables live in their own `vyne` schema inside the same
database the other two systems use, so nothing collides with the Dearborn
workbench's tables or the AS/400's.

Set DATABASE_URL in the repo-root .env, e.g. the Supabase connection string.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, MetaData, String, Text,
    create_engine, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# <repo root>/.env — vyne_mock/backend/database.py is two levels below it
_here = Path(__file__).resolve()
if len(_here.parents) > 2:          # not the case inside a flat Docker /app layout
    load_dotenv(_here.parents[2] / ".env")

SCHEMA = "vyne"

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


class VyneClaim(Base):
    __tablename__ = "vyne_claims"

    id              = Column(Integer, primary_key=True, index=True)
    tracking_id     = Column(String, unique=True, nullable=False, index=True)
    submission_date = Column(String)
    payer_id        = Column(String)
    payer_name      = Column(String)
    primary_payer   = Column(String)   # other-payer loop 2320 — COB primary
    is_cob          = Column(Boolean, default=False)
    subscriber_id   = Column(String)
    subscriber_name = Column(String)
    provider_npi    = Column(String)
    provider_name   = Column(String)
    patient_name    = Column(String)
    cdt_codes       = Column(Text)   # JSON array
    procedure_date  = Column(String)
    billed_amount   = Column(Float)
    status          = Column(String, default="RECEIVED")
    response_code   = Column(String)
    response_message = Column(Text)
    envelope_errors = Column(Text)   # JSON array — why an envelope was rejected
    raw_edi         = Column(Text)
    procedures      = Column(Text)   # JSON array
    filename           = Column(String)

    # Supporting documents sent with the claim (JSON): clinical narrative,
    # treatment history, EOB summary, COB questionnaire, attachments...
    patient_details    = Column(Text)

    # Hand-off to the payer's AS/400 adjudication system
    as400_claim_no   = Column(String)
    as400_screen_url = Column(String)
    forwarded_at     = Column(DateTime)

    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))


def create_tables():
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()


def _migrate_add_columns():
    """Add columns missing from a table created by an older version (non-destructive)."""
    new_cols = [
        ("primary_payer",    "VARCHAR"),
        ("is_cob",           "BOOLEAN"),
        ("envelope_errors",  "TEXT"),
        ("as400_claim_no",   "VARCHAR"),
        ("as400_screen_url", "VARCHAR"),
        ("forwarded_at",     "TIMESTAMP"),
        ("patient_details",  "TEXT"),
    ]
    with engine.begin() as conn:
        for col, col_type in new_cols:
            conn.execute(text(
                f'ALTER TABLE "{SCHEMA}".vyne_claims ADD COLUMN IF NOT EXISTS {col} {col_type}'
            ))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
