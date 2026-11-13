"""
Dental claim adjudication agent using Azure OpenAI GPT-4o with tool/function calling.

Flow:
  1. Receive gold-layer structured claim data
  2. Agent calls DB lookup tools to verify member, plan, coverage rules, fee schedule
  3. Agent reasons about eligibility, waiting periods, COB, predetermination requirements
  4. Returns a structured decision JSON with full justification and data sources
"""
import json
import os
from datetime import date

from openai import AzureOpenAI
from sqlalchemy.orm import Session

from database import Member, Plan, CoverageRule, FeeSchedule, Claim, OrthoTreatmentHistory, EobRecord, SessionLocal

# ── Azure OpenAI client (lazy — built on first adjudication call) ─────────────
# Initializing at import time would crash the whole app if env vars aren't set.

_client: AzureOpenAI | None = None


def _get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
    return _client


DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


# ── Tool definitions (OpenAI function-calling format) ─────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_member",
            "description": (
                "Look up an insurance member by their subscriber ID. "
                "Returns name, date of birth, plan_id, enrollment_date, "
                "group_id, secondary_insurance, and is_active status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subscriber_id": {
                        "type": "string",
                        "description": "Subscriber ID from the claim form, e.g. HCSC-TX-88301124",
                    }
                },
                "required": ["subscriber_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_plan",
            "description": (
                "Look up an insurance plan by plan_id. "
                "Returns plan_name, plan_type, tier, annual_max, deductible, "
                "coinsurance_pct, and lifetime_ortho_max."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Plan ID from the member record, e.g. PPO-SILVER-TX",
                    }
                },
                "required": ["plan_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_coverage_rules",
            "description": (
                "Look up the coverage rules that apply to a CDT procedure code under a specific plan. "
                "Matches on the first 4 characters of the CDT code (the prefix). "
                "Returns coverage_pct, requires_predetermination, requires_xray, "
                "waiting_period_months, and min_amount_for_predet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "description": "Plan ID, e.g. PPO-SILVER-TX"},
                    "cdt_code": {"type": "string", "description": "Full CDT code, e.g. D2740"},
                },
                "required": ["plan_id", "cdt_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_fee_schedule",
            "description": (
                "Look up the contracted fee for a CDT code under a plan. "
                "Returns procedure_name, ucr_fee (billed rate), and ppo_allowed_fee (contracted rate). "
                "The plan pays coinsurance_pct of ppo_allowed_fee after the deductible."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "description": "Plan ID, e.g. PPO-SILVER-TX"},
                    "cdt_code": {"type": "string", "description": "Full CDT code, e.g. D2740"},
                },
                "required": ["plan_id", "cdt_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_ortho_history",
            "description": (
                "Look up orthodontic treatment history for a subscriber. "
                "Returns patient_dob, treatment_start_date, total_treatment_months, "
                "months_completed, prior_plan_id, prior_plan_paid, prior_plan_monthly_rate, "
                "and clinical_narrative (doctor's justification notes). "
                "Call this for ANY claim containing D806x, D808x, or D809x CDT codes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subscriber_id": {"type": "string", "description": "Subscriber ID from the claim"}
                },
                "required": ["subscriber_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_primary_eob",
            "description": (
                "Look up the EOB (Explanation of Benefits) from the primary insurance plan. "
                "Returns primary_plan_name, billed_amount, primary_paid_amount, payment_type "
                "(lump_sum or monthly), monthly_amount, months_paid, and remaining_balance. "
                "Call this when cob_flag is true to calculate secondary plan obligations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subscriber_id": {"type": "string", "description": "Subscriber ID from the claim"}
                },
                "required": ["subscriber_id"],
            },
        },
    },
]


# ── Tool handler — dispatches to SQLAlchemy queries ───────────────────────────

def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy model instance to a plain dict."""
    d = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    d.pop("id", None)  # internal PK not useful to the agent
    return d


def handle_tool(name: str, args: dict, db: Session) -> dict:
    if name == "lookup_member":
        row = db.query(Member).filter_by(subscriber_id=args["subscriber_id"]).first()
        return _row_to_dict(row) if row else {"error": f"Member not found: {args['subscriber_id']}"}

    if name == "lookup_plan":
        row = db.query(Plan).filter_by(plan_id=args["plan_id"]).first()
        return _row_to_dict(row) if row else {"error": f"Plan not found: {args['plan_id']}"}

    if name == "lookup_coverage_rules":
        prefix = args["cdt_code"][:4]
        row = db.query(CoverageRule).filter_by(
            plan_id=args["plan_id"], cdt_prefix=prefix
        ).first()
        return _row_to_dict(row) if row else {"error": f"No coverage rule for {args['cdt_code']} on {args['plan_id']}"}

    if name == "lookup_fee_schedule":
        row = db.query(FeeSchedule).filter_by(
            plan_id=args["plan_id"], cdt_code=args["cdt_code"]
        ).first()
        return _row_to_dict(row) if row else {"error": f"No fee schedule for {args['cdt_code']} on {args['plan_id']}"}

    if name == "lookup_ortho_history":
        rows = db.query(OrthoTreatmentHistory).filter_by(subscriber_id=args["subscriber_id"]).all()
        if not rows:
            return {"error": f"No ortho history found for {args['subscriber_id']}"}
        return [_row_to_dict(r) for r in rows]

    if name == "lookup_primary_eob":
        row = db.query(EobRecord).filter_by(subscriber_id=args["subscriber_id"]).first()
        return _row_to_dict(row) if row else {"error": f"No EOB found for {args['subscriber_id']}"}

    return {"error": f"Unknown tool: {name}"}


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are an expert dental insurance adjudicator for the Dearborn Group / HCSC.

Today's date is {date.today().isoformat()}.

Your job is to review a structured dental claim and decide: APPROVED, DENIED, or NEEDS_REVIEW.

## How to adjudicate:

Step 1 — Verify the member
  Call lookup_member with the subscriber_id from the claim.
  Check is_active = true. Note the enrollment_date and plan_id.
  If secondary_insurance is set, the claim has COB — do NOT auto-flag yet; check for ortho codes first (see complex cases below).

Step 2 — Get the plan details
  Call lookup_plan with the plan_id from the member record.
  Note: annual_max, deductible, coinsurance_pct, lifetime_ortho_max.

Step 3 — For each CDT code in the claim:
  Call lookup_coverage_rules(plan_id, cdt_code)
  Call lookup_fee_schedule(plan_id, cdt_code)
  If any code starts with D806, D808, or D809, ALSO call lookup_ortho_history(subscriber_id).

Step 4 — Check every rule:
  a) WAITING PERIOD: months_elapsed = (procedure_date - enrollment_date).days // 30
     If months_elapsed < waiting_period_months → DENY with code W-12
  b) PREDETERMINATION: if requires_predetermination = true AND billed_amount >= min_amount_for_predet
     AND predetermination_number is null → DENY with code P-02
  c) X-RAY: if requires_xray = true AND xray_present = false → DENY with code A-07
  e) MEMBER INACTIVE: if is_active = false → DENY with code E-01

Step 5 — Calculate approved amount (if approving):
  approved_amount = ppo_allowed_fee * coinsurance_pct
  (Assume deductible has not been met for conservatism unless deductible_met = true in claim data.)

## Special Complex Cases — Where Human Judgment Beats Automation

### Scenario 1 — Orthodontic CDT Coding Ambiguity
If CDT codes contain D8060, D8080, or D8090:
- ALWAYS call lookup_ortho_history(subscriber_id)
- Expected age ranges: D8060 (Interceptive) = age 6-11 | D8080 (Comprehensive Adolescent) = 12-17 | D8090 (Comprehensive Adult) = 18+
- Calculate patient age from patient_dob in the history record vs today's date
- If patient age DOES NOT match the expected CDT code age range:
  * Read the clinical_narrative carefully
  * If narrative provides specific medical justification (skeletal maturity staging, cephalometric findings, specialist recommendation) → return NEEDS_REVIEW with complex_case_type="ORTHO_AMBIGUITY", denial_codes=["ORTHO-01"]
  * Explain in justification: what age the patient is, what the code expects, and what the narrative says
  * Set human_reviewer_guidance to step-by-step instructions: verify cephalometric report, confirm CS4 staging, contact Dr. Holt for records, override CDT code if justified
  * A pure rule-based system would auto-deny this. Your role is to flag it for a specialist who can read the narrative.
- If age matches → process normally under standard rules.

### Scenario 2 — Work-in-Progress Orthodontic COB (Mid-Treatment Insurance Switch)
If CDT codes contain D806x/D808x/D809x AND cob_flag is true:
- Call lookup_ortho_history(subscriber_id)
- If months_completed > 0 AND prior_plan_paid > 0:
  * This is a WIP ortho case — patient switched insurers mid-treatment
  * Calculate: remaining_months = total_treatment_months - months_completed
  * Calculate: prorated_obligation = (remaining_months / total_treatment_months) * plan's lifetime_ortho_max
  * Net obligation = max(0, prorated_obligation - prior_plan_paid)
  * Return NEEDS_REVIEW with complex_case_type="WIP_ORTHO_COB", denial_codes=["WIP-01"]
  * In justification: show the full calculation — prior paid, remaining months, prorated amount, net obligation
  * Set human_reviewer_guidance: call Cigna to verify paid amount, set up prorated payment schedule, document in system
  * A computer cannot verify what the prior insurer paid or build a custom payment schedule.

### Scenario 3 — Cross-Plan Coordination of Benefits
If cob_flag is true AND no ortho codes (D806x/D808x/D809x) present:
- Call lookup_primary_eob(subscriber_id)
- Check payment_type:
  * "lump_sum": secondary obligation = remaining_cob × coinsurance_pct, capped by fee schedule and annual_max
  * "monthly": secondary plan must honor its monthly schedule without exceeding remaining_balance
- Verify: primary_paid_amount + secondary_obligation must NOT exceed billed_amount (no overpayment)
- Always set complex_case_type="CROSS_PLAN_COB" (it describes the case, not the outcome)

HUMAN INPUT. A technician may have re-opened this claim. The claim message can carry:
  * "human_overrides": figures the technician corrected, each with the original and
    the edited value. Treat the EDITED value as authoritative — use it in every
    calculation, even where the database or EOB lookup shows a different figure.
    Say in the justification which values were edited and what difference it made.
    If an edited value contradicts the primary EOB on file, note the discrepancy
    for the reviewer but do not refuse to calculate.
  * "secondary_owes_override" (inside human_overrides): the technician has set the amount
    the secondary plan should pay. Use it as approved_amount, then check it against
    the no-overpayment rule (primary paid + this amount must not exceed billed) and
    the annual maximum, and say plainly whether it is acceptable and why. If it
    differs from your own calculation, show both figures.
  * "reviewer_note": the technician's own explanation, which can include an edited
    version of your earlier justification or action steps. Where the technician has
    rewritten a conclusion, address it directly rather than repeating your old text. Read it and respond to it.
  * "uploaded_documents": extra evidence (name, text). Read it and use it — a court
    decree, a corrected EOB, a clinical note. Cite each document you relied on by
    file name. If a document could not be read, say so.
If none of these are present, this is a first run; ignore this paragraph.

LIABILITY FIRST. The claim message includes a "cobd" object: the client's COB
liability flowchart already walked for this claim. Read it before any arithmetic.
  * cobd.hcsc_role = "SECONDARY": HCSC pays after the other plan. Continue below.
  * cobd.hcsc_role = "PRIMARY": HCSC should have paid first, so the other payer's
    payment is the error. Do NOT compute a secondary payment. Return NEEDS_REVIEW,
    complex_case_type="CROSS_PLAN_COB", denial_codes=["COB-05"], approved_amount=null.
    Justification names the flowchart rule and node (e.g. "Rule 2, birthday rule").
    Guidance: reprocess as primary, then recover the other payer's payment.
  * cobd.hcsc_role = "UNDETERMINED": the flow cannot settle it alone. Return
    NEEDS_REVIEW, denial_codes=["COB-06"], approved_amount=null. Justification
    states which rule or branch applies (cobd.terminal) and what evidence is missing.
In every case quote cobd.terminal.detail and the nodes in cobd.path in the justification.

NOW DECIDE. Do not escalate reflexively — escalate only when something genuinely
blocks a decision. The payer's AS/400 already suspended this claim because it has
no rule for converting between settlement models; your job is to work out whether
that conversion is actually a problem here.

Return APPROVED when ALL of these hold:
  * the primary EOB is on file and its paid amount is known
  * primary_paid_amount + secondary_obligation <= billed_amount (no overpayment)
  * secondary_obligation <= the plan's annual_max
  * EITHER the secondary settles lump_sum, OR its monthly schedule can clear the
    obligation inside the term: ceil(secondary_obligation / monthly_cap) <= term_months
  Confidence 0.90–0.95. denial_codes = []. Set approved_amount to the obligation.
  In the justification, state plainly that the coordination resolves without a
  manual override and show the arithmetic that proves it.

Return NEEDS_REVIEW only when one of these is true — and name which one:
  * the primary EOB is missing, or the paid amount cannot be established
  * the combined payments would exceed the billed amount (overpayment risk)
  * the obligation exceeds the plan's annual_max or lifetime maximum
  * the monthly schedule CANNOT clear the obligation inside the term, so a human
    must override the disbursement schedule → denial_codes = ["COB-03"]
  * the figures in the claim contradict the figures on the EOB
  Confidence 0.70–0.88, and say in the justification exactly what is blocking.

A clean coordination is an APPROVED recommendation a technician confirms in one
click. That is the normal outcome, not the exception.

YOU MUST DO THE ARITHMETIC. Do not describe the method and stop — a reviewer
needs the figures. Specifically:

- Compute the actual numbers and put them in the justification:
    remaining_balance = primary_allowed_amount − primary_paid_amount
    secondary_obligation = remaining_balance × coinsurance_pct (cap with fee schedule + annual max)
  Round to the nearest cent. Write them out with dollar signs, e.g.
    "$1,100 allowed − $442 primary paid = $658 remaining. HCSC 50% → $329.
     Verify $442 + $329 ≤ billed and obligation ≤ plan annual max."
- Set approved_amount to the calculated secondary obligation (the capped figure).
  This is the recommended payment the reviewer will verify — NOT null. Leave it
  null ONLY if the EOB is missing and you genuinely cannot compute it.
- If the claim data shows secondary_settlement = "MONTHLY" with a monthly_cap
  and term_months, also state whether the schedule can clear the obligation:
    months_needed = ceil(secondary_obligation ÷ monthly_cap)
  and say plainly whether that fits inside term_months or needs an override.
- human_reviewer_guidance: return it as a JSON ARRAY of strings, one step per
  element, with NO leading numbers — the UI numbers them. On an APPROVED
  recommendation these are the confirmation steps a technician ticks off; on a
  NEEDS_REVIEW they are the work needed to unblock it. Quote the real figures
  and the real EOB number — not generic advice. For example:
    [
      "Retrieve EOB DELTA-EOB-2026-23487 from Delta Dental of Illinois and confirm the paid amount of $442.00.",
      "Confirm remaining COB balance $1,100.00 allowed − $442.00 primary = $658.00.",
      "Apply HCSC coinsurance 50% → obligation $329.00 (within annual max).",
      "Verify $442.00 + $329.00 = $771.00 ≤ $1,190.00 billed — no overpayment.",
      "Authorise the coordinated payment of $329.00.",
      "Record the COB coordination against both member records."
    ]

Never return NEEDS_REVIEW with an empty or generic justification. If you are
escalating, the reader must be able to see the specific blocker in one sentence.

Step 6 — Return your decision as a JSON object with this exact structure:
{{
  "decision": "APPROVED" | "DENIED" | "NEEDS_REVIEW",
  "confidence": <float 0.0-1.0>,
  "justification": "<plain English explanation, 3-5 sentences>",
  "complex_case_type": "ORTHO_AMBIGUITY" | "WIP_ORTHO_COB" | "CROSS_PLAN_COB" | null,
  "human_reviewer_guidance": ["<step>", "<step>"],   // array of strings, unnumbered
  "data_sources": [
    {{"table": "<table name>", "row": {{...entire row dict...}}}}
  ],
  "denial_codes": ["W-12", "P-02"],
  "approved_amount": <float or null>
}}

Return ONLY the JSON object. No markdown, no extra text.
"""


# ── Main adjudication function ────────────────────────────────────────────────

def adjudicate(claim_id: str, gold_data: dict) -> dict:
    """
    Run the GPT-4o agent tool-use loop against the DB.
    Saves the decision JSON back to the Claim row.
    Returns the decision dict.
    """
    db = SessionLocal()

    claim_for_agent = dict(gold_data)
    if gold_data.get("cob_flag"):
        from cobd import determine as cobd_determine

        claim_for_agent["cobd"] = cobd_determine(gold_data)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here is the structured claim to adjudicate:\n\n"
                + json.dumps(claim_for_agent, indent=2)
            ),
        },
    ]

    raw = ""
    agent_error: str | None = None

    # Fail fast and clearly when the model isn't configured at all, rather than
    # letting it surface as an unexplained "could not produce a decision".
    if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
        agent_error = (
            "AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT are not set. "
            "The agent cannot call the model."
        )

    try:
        if agent_error:
            raise RuntimeError(agent_error)

        client = _get_client()  # inside try so client init errors are caught too

        # Tool-use loop — capped at 10 iterations to prevent infinite loops
        for _ in range(10):
            response = client.chat.completions.create(
                model=DEPLOYMENT,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0,
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                # Append assistant message as a plain dict (SDK objects can fail serialization)
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                # Execute each requested tool and append its result
                for tc in msg.tool_calls:
                    tool_args = json.loads(tc.function.arguments)
                    result = handle_tool(tc.function.name, tool_args, db)
                    print(f"[Agent] tool={tc.function.name} args={tool_args} → {result}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
            else:
                # Model produced its final answer — exit the loop
                raw = msg.content.strip() if msg.content else ""
                break

    except Exception as exc:
        agent_error = agent_error or f"{type(exc).__name__}: {exc}"
        print(f"[Agent] Azure OpenAI error: {agent_error}")
        raw = ""

    # Parse the decision JSON returned by the model
    try:
        # Strip markdown code fences if the model wrapped the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        decision = json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError, ValueError):
        if agent_error:
            justification = (
                f"The agent did not run: {agent_error} "
                "This is a configuration problem, not a finding about the claim — "
                "the claim has not been assessed."
            )
        else:
            justification = (
                "The model returned a response that could not be parsed as a decision. "
                "The claim has not been assessed."
            )
        decision = {
            "decision": "NEEDS_REVIEW",
            "confidence": 0.0,
            "justification": justification,
            "agent_error": agent_error,
            "raw_response": raw[:500] if raw else None,
            "data_sources": [],
            "denial_codes": [],
            "approved_amount": None,
        }

    # Save decision to DB
    claim = db.query(Claim).filter_by(claim_id=claim_id).first()
    if claim:
        claim.status = "ADJUDICATED"
        claim.decision_json = json.dumps(decision)
        db.commit()

    db.close()
    print(f"[Agent] claim_id={claim_id} → decision={decision.get('decision')}")
    return decision
