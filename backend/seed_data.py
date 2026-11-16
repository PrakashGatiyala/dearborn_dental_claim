from database import SessionLocal, create_tables, Plan, Member, PlanMember, CoverageRule, FeeSchedule, OrthoTreatmentHistory, EobRecord


def seed():
    create_tables()
    db = SessionLocal()

    plans = [
        ("PPO-SILVER-CA", "HCSC PPO Silver CA", "Silver", 2000, 150, .5, 0),
        ("PPO-GOLD-AZ", "HCSC PPO Gold AZ", "Gold", 2500, 150, .5, 3000),
        ("PPO-GOLD-TX", "HCSC PPO Gold TX", "Gold", 2000, 150, .5, 3000),
        ("PPO-SILVER-FL", "HCSC PPO Silver FL", "Silver", 2000, 150, .5, 0),
        ("PPO-BRONZE-IL", "HCSC PPO Bronze IL", "Bronze", 1000, 200, .5, 0),
        ("PPO-GOLD-NY", "HCSC PPO Gold NY", "Gold", 2500, 150, .5, 0),
    ]
    for pid, name, tier, annual, ded, coins, ortho in plans:
        if not db.query(Plan).filter_by(plan_id=pid).first():
            db.add(Plan(plan_id=pid, plan_name=name, plan_type="PPO", tier=tier,
                        annual_max=annual, deductible=ded, coinsurance_pct=coins,
                        lifetime_ortho_max=ortho))

    members = [
        ("HCSC-CA-62004117", "Ethan Miller", "1982-02-18", "PPO-SILVER-CA", "2024-01-01", "GRP-NL-2024-CA", None),
        ("HCSC-AZ-73190542", "Sofia Ramirez", "1991-06-09", "PPO-GOLD-AZ", "2025-01-01", "GRP-CHA-2025-AZ", None),
        ("HCSC-TX-80421673", "Olivia Chen", "1988-10-12", "PPO-GOLD-TX", "2024-03-01", "GRP-BME-2024-TX", "Cigna Dental PPO"),
        ("HCSC-FL-61590834", "Noah Thompson", "1976-03-27", "PPO-SILVER-FL", "2023-07-01", "GRP-SMG-2023-FL", None),
        ("HCSC-IL-55031826", "Ava Brooks", "1969-12-04", "PPO-BRONZE-IL", "2025-01-01", "GRP-LFP-2025-IL", None),
        ("HCSC-NY-69421058", "Mia Johnson", "1984-08-31", "PPO-GOLD-NY", "2024-01-01", "GRP-HDM-2024-NY", None),
    ]
    for sid, name, dob, pid, enroll, group, secondary in members:
        if not db.query(Member).filter_by(subscriber_id=sid).first():
            db.add(Member(subscriber_id=sid, name=name, dob=dob, plan_id=pid,
                          enrollment_date=enroll, group_id=group,
                          secondary_insurance=secondary, is_active=True))

    plan_members = [
        ("PPO-SILVER-CA", "HCSC-CA-62004117", "Ethan Miller", "subscriber", "1982-02-18", "HCSC-CA-62004117-01"),
        ("PPO-GOLD-AZ", "HCSC-AZ-73190542", "Sofia Ramirez", "subscriber", "1991-06-09", "HCSC-AZ-73190542-01"),
        ("PPO-GOLD-TX", "HCSC-TX-80421673", "Olivia Chen", "subscriber", "1988-10-12", "HCSC-TX-80421673-01"),
        ("PPO-SILVER-FL", "HCSC-FL-61590834", "Noah Thompson", "subscriber", "1976-03-27", "HCSC-FL-61590834-01"),
        ("PPO-BRONZE-IL", "HCSC-IL-55031826", "Ava Brooks", "subscriber", "1969-12-04", "HCSC-IL-55031826-01"),
        ("PPO-GOLD-NY", "HCSC-NY-69421058", "Mia Johnson", "subscriber", "1984-08-31", "HCSC-NY-69421058-01"),
    ]
    for pid, sid, name, rel, dob, mid in plan_members:
        if not db.query(PlanMember).filter_by(member_id=mid).first():
            db.add(PlanMember(plan_id=pid, subscriber_id=sid, member_name=name,
                              relationship=rel, dob=dob, member_id=mid))

    rules = [
        ("PPO-SILVER-CA", "D274", "Crown", .5, False, True, 0, 1600),
        ("PPO-SILVER-CA", "D012", "Preventive", 1.0, False, False, 0, 0),
        ("PPO-GOLD-AZ", "D333", "Endodontics", .5, False, True, 0, 0),
        ("PPO-GOLD-AZ", "D022", "Diagnostic", 1.0, False, False, 0, 0),
        ("PPO-GOLD-TX", "D809", "Orthodontics", .5, True, False, 0, 0),
        ("PPO-GOLD-TX", "D866", "Orthodontics", .5, False, False, 0, 0),
        ("PPO-SILVER-FL", "D714", "Extraction", .8, False, True, 0, 0),
        ("PPO-SILVER-FL", "D022", "Diagnostic", 1.0, False, False, 0, 0),
        ("PPO-BRONZE-IL", "D601", "Implant", .5, True, True, 24, 500),
        ("PPO-BRONZE-IL", "D795", "Bone Graft", .5, False, True, 0, 0),
        ("PPO-GOLD-NY", "D434", "Periodontics", .8, False, True, 0, 0),
        ("PPO-GOLD-NY", "D018", "Periodontal Evaluation", 1.0, False, False, 0, 0),
    ]
    for pid, prefix, cat, pct, pred, xray, wait, min_pred in rules:
        if not db.query(CoverageRule).filter_by(plan_id=pid, cdt_prefix=prefix).first():
            db.add(CoverageRule(plan_id=pid, cdt_prefix=prefix,
                                procedure_category=cat, coverage_pct=pct,
                                requires_predetermination=pred, requires_xray=xray,
                                waiting_period_months=wait,
                                min_amount_for_predet=min_pred))

    fees = [
        ("PPO-SILVER-CA", "D2740", "Crown – porcelain/ceramic substrate", 1450, 1180),
        ("PPO-SILVER-CA", "D0120", "Periodic oral evaluation", 65, 45),
        ("PPO-GOLD-AZ", "D3330", "Root canal – molar", 1180, 1000),
        ("PPO-GOLD-AZ", "D0220", "Periapical radiographic image", 42, 30),
        ("PPO-GOLD-TX", "D8090", "Comprehensive orthodontic treatment – adult", 6200, 5600),
        ("PPO-GOLD-TX", "D8660", "Pre-orthodontic examination", 175, 135),
        ("PPO-SILVER-FL", "D7140", "Extraction, erupted tooth or exposed root", 295, 250),
        ("PPO-SILVER-FL", "D0220", "Periapical radiographic image", 40, 30),
        ("PPO-BRONZE-IL", "D6010", "Endosseous implant body placement", 2650, 2350),
        ("PPO-BRONZE-IL", "D7953", "Bone replacement graft", 650, 500),
        ("PPO-GOLD-NY", "D4341", "Scaling and root planing – four or more teeth", 1050, 900),
        ("PPO-GOLD-NY", "D0180", "Comprehensive periodontal evaluation", 120, 100),
    ]
    for pid, code, name, ucr, allowed in fees:
        if not db.query(FeeSchedule).filter_by(plan_id=pid, cdt_code=code).first():
            db.add(FeeSchedule(plan_id=pid, cdt_code=code, procedure_name=name,
                               ucr_fee=ucr, ppo_allowed_fee=allowed))

    db.commit()
    db.close()
    print("Seed data inserted successfully.")
    print("Plans: 6 | Subscribers: 6 | Plan members: 6 | Rules: 12 | Fees: 12")
    seed_complex_cases()


def seed_complex_cases():
    db = SessionLocal()

    # ── Scenario 1: Ortho Coding Ambiguity ──────────────────────────────────────
    if not db.query(OrthoTreatmentHistory).filter_by(subscriber_id="HCSC-TX-80421673", patient_name="Lucas Chen").first():
        db.add(OrthoTreatmentHistory(
            subscriber_id           = "HCSC-TX-80421673",
            patient_name            = "Lucas Chen",
            patient_dob             = "2017-03-15",
            treatment_start_date    = "2026-06-01",
            total_treatment_months  = 24,
            months_completed        = 0,
            prior_plan_id           = None,
            prior_plan_name         = None,
            prior_plan_paid         = 0.0,
            prior_plan_monthly_rate = 0.0,
            clinical_narrative      = (
                "Patient is 9 years old but presents with skeletal Class III malocclusion "
                "with advanced bone maturity equivalent to a 13-year-old adolescent as confirmed "
                "by cephalometric radiograph (Cervical Vertebral Maturation stage CS4). "
                "Interceptive treatment (D8060) is insufficient given the severity of the "
                "anteroposterior discrepancy (-6mm). Attending orthodontist Dr. Patricia Holt, "
                "DDS recommends full comprehensive treatment (D8090) to prevent surgical "
                "intervention at adulthood. Treatment plan attached."
            ),
        ))

    # ── Scenario 2: Work-in-Progress Ortho COB ──────────────────────────────────
    if not db.query(OrthoTreatmentHistory).filter_by(subscriber_id="HCSC-TX-80421673", patient_name="Olivia Chen").first():
        db.add(OrthoTreatmentHistory(
            subscriber_id           = "HCSC-TX-80421673",
            patient_name            = "Olivia Chen",
            patient_dob             = "1988-10-12",
            treatment_start_date    = "2024-09-01",
            total_treatment_months  = 24,
            months_completed        = 12,
            prior_plan_id           = "CIGNA-PPO-TX",
            prior_plan_name         = "Cigna Dental PPO (Prior Employer)",
            prior_plan_paid         = 2800.0,
            prior_plan_monthly_rate = 233.33,
            clinical_narrative      = (
                "Patient enrolled in comprehensive orthodontic treatment (D8090) under prior "
                "employer Cigna Dental PPO effective 2024-09-01. Patient changed employment "
                "2025-09-01 and is now covered under HCSC PPO Gold TX. Braces placed, "
                "12 of 24 months completed. Cigna paid $2,800 of $5,600 allowed (lump-sum "
                "50% upfront model). Requesting HCSC to cover remaining 12 months at "
                "prorated lifetime ortho benefit."
            ),
        ))

    # ── Scenario 3: Cross-Plan COB EOB record ───────────────────────────────────
    import json as _json
    if not db.query(EobRecord).filter_by(subscriber_id="HCSC-TX-80421673").first():
        db.add(EobRecord(
            subscriber_id       = "HCSC-TX-80421673",
            eob_number          = "CIGNA-EOB-2026-44921",
            primary_plan_id     = "CIGNA-PPO-TX",
            primary_plan_name   = "Cigna Dental PPO",
            cdt_codes           = _json.dumps(["D8090"]),
            billed_amount           = 6200.0,
            primary_paid_amount     = 1500.0,
            primary_allowed_amount  = 6200.0,
            payment_type        = "lump_sum",
            monthly_amount      = None,
            months_paid         = None,
            claim_date          = "2025-09-15",
            remaining_balance   = 4700.0,
        ))

    db.commit()
    db.close()
    print("Complex case seed data inserted.")


if __name__ == "__main__":
    seed()
