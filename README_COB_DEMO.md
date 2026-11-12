# COB Claim Demo — three systems

```
vyne_sender.py  ──►  VYNE (:8001 / :5174)  ──►  AS/400 (:8002 / :5175)  ──►  DEARBORN (:8000 / :5173)
                     clearinghouse               payer adjudication          agent workbench
                     validates + routes          runs the edit sequence      works the suspended ones
                     does NOT adjudicate         green screen                AI analysis
```

Every claim in the dataset is a **Coordination of Benefits** claim — the patient is
covered by two plans. The split that matters:

| Case | What happens | Where it ends up |
|---|---|---|
| `SIMPLE_COB` | Both plans settle the same way. Remaining balance × secondary coinsurance. | AS/400 pays it. Never reaches Dearborn. |
| `CROSS_PLAN_COB` | Primary paid a lump sum; secondary only disburses on a capped monthly schedule. The AS/400 has no rule to convert between them. | Suspends on **COB-03**, referred to Dearborn. |

## Run it

```
start_demo.bat
```

Or by hand, six terminals:

```
python cob_edi_generator.py --count 12
python seed_cob_claims.py

cd backend            && uvicorn main:app --port 8000 --reload
cd vyne_mock\backend  && uvicorn main:app --port 8001 --reload
cd as400\backend      && uvicorn main:app --port 8002 --reload

cd frontend            && npm run dev     # :5173
cd vyne_mock\frontend  && npm run dev     # :5174
cd as400\frontend      && npm install && npm run dev   # :5175  (first run installs)
```

Then send claims:

```
python vyne_sender.py --interval 30     # one every 30s, good for a live demo
python vyne_sender.py --all             # everything at once
```

Reset between runs: `python reset_demo.py`

## The AS/400 screen

Sign on at <http://localhost:5175> with **OPER01 / DEMO123**.

| Screen | What it is |
|---|---|
| `CLMMENU` | Main menu, claim file summary, option entry + command line |
| `CLM210` | Work with COB claims — subfile list, `Opt` column, position-to, status filter |
| `CLM220` | Claim detail — COB settlement rules and benefit calculation |
| `CLM225` | Adjudication edit trace — the numbered edit sequence, and which one failed |
| `CLM230` | COB reconciliation worksheet — the arithmetic and the manual steps |

Function keys work for real: **F3** exit, **F5** refresh, **F6** adjudicate now,
**F8** toggle edit trace, **F9** refer to the workbench, **F10** release,
**F11** worksheet, **F12** cancel. Enter applies the option you typed in `Opt`.

## The edit sequence

The AS/400 runs a fixed numbered sequence. A failure stops it and suspends the claim.

| Seq | Edit | Suspends with |
|---|---|---|
| 0100 | Claim data completeness | `EDI-01` |
| 0220 | Primary payer EOB on file | `COB-01` |
| 0310 | Overpayment guard | `COB-02` |
| 0450 | Secondary coinsurance on file | `COB-04` |
| **0640** | **COB settlement reconciliation** | **`COB-03`** ← the one this demo is about |
| 0710 | Combined payment verification | `COB-02` |
| 0900 | Adjudication complete | — pays |

## Dataset

`cob_edi_generator.py` writes real 837D files to `datasets/cob_edi/`, each carrying:

- `SBR*S` secondary subscriber loop (destination payer) and `SBR*P` other-payer loop 2320
- `AMT*D` / `AMT*B6` — what the primary already paid and allowed
- `REF*F8` — the primary payer's EOB reference
- `REF*9F SETTLE:LUMP_SUM|MONTHLY` — each plan's settlement rule
- `REF*G1 MONTHLYCAP:` / `REF*G3 TERMMONTHS:` — the secondary's disbursement limits
- `SVD` / `CAS` — the primary's line-level adjudication

`manifest.json` records the expected outcome per claim, so you can check the
AS/400 behaved correctly.

Options: `--count`, `--cross-plan-ratio` (default 0.4), `--seed`, `--out`.

### Seeding — required before the agent will work

`seed_cob_claims.py` reads the manifest and inserts, for every generated claim,
the rows the Dearborn agent's six lookup tools need: `Member`, `PlanMember`,
`CoverageRule`, `FeeSchedule` and `EobRecord`.

**Run it every time you regenerate the dataset.** Subscriber IDs change on each
run, and if the subscriber isn't in the member table every tool call returns
"not found" — the agent then has nothing to reason over and returns
`NEEDS_REVIEW` at 0% confidence with no analysis.

## Troubleshooting the agent

`NEEDS_REVIEW` at **0% confidence** is not a verdict about the claim — it is the
fallback the agent returns when it could not run at all. The justification text
now says which of these it was:

| Cause | Fix |
|---|---|
| `AZURE_OPENAI_API_KEY / ENDPOINT are not set` | set them in `.env` |
| A 401 from Azure | the key is dead or rotated — issue a new one |
| Tool lookups all return "not found" | run `python seed_cob_claims.py` |

The backend window prints `[Agent] tool=… → …` for each lookup. If those lines
show `{"error": "Member not found: …"}`, it is the seeding problem.

## Config

All service URLs are environment variables with localhost defaults:

| Variable | Default | Used by |
|---|---|---|
| `VYNE_API_URL` | `http://localhost:8001` | sender, reset |
| `AS400_API_URL` | `http://localhost:8002` | Vyne forwarder, reset |
| `DEARBORN_API_URL` | `http://localhost:8000` | AS/400 referrer, reset |
| `AS400_PORTAL_URL` | `http://localhost:5175` | links back from Vyne |
| `DEARBORN_PORTAL_URL` | `http://localhost:5173` | links from the AS/400 |
| `AS400_ADJUDICATION_DELAY` | `12` (seconds) | how long a claim sits before the batch picks it up |
| `COB_DATASET_DIR` | `datasets/cob_edi` | sender |
