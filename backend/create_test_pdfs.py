"""
Generate two test PDFs for the Patricia Nguyen claim scenario (expected: APPROVED).

Text layout matches the gold-layer regex patterns in medallion.py exactly:
  - Each field label is on its own line; value is on the NEXT line.
  - CDT codes appear in the procedures section.
  - Dollar amounts include the largest total so billed_amount parses correctly.
  - The proof PDF mentions radiograph/bitewing/periapical → xray_present = True.

Run inside the backend container:
    docker compose exec backend python create_test_pdfs.py

Output:  /app/test_pdfs/   (visible as ./backend/test_pdfs/ on host)
"""
import fitz  # PyMuPDF — already in requirements.txt
from pathlib import Path

OUTPUT_DIR = Path("/app/test_pdfs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONTSIZE = 10
LINE_HEIGHT = 14   # vertical gap between lines (points)
LEFT_X = 50
PAGE_W, PAGE_H = 612, 792


def make_pdf(lines: list, output_path: Path) -> None:
    """
    Write a text PDF using insert_text() (one call per line).
    insert_textbox() does not write to the content stream in PyMuPDF 1.24 —
    so we use insert_text() with explicit y-coordinates so get_text() can
    extract the text back with newlines preserved.
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = 60  # top margin

    for line in lines:
        if y > PAGE_H - 40:          # bottom margin — add new page
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            y = 60
        page.insert_text(
            (LEFT_X, y),
            line,
            fontsize=FONTSIZE,
            fontname="helv",
            color=(0, 0, 0),
        )
        y += LINE_HEIGHT

    doc.save(str(output_path))
    doc.close()
    print(f"  Created: {output_path}")


# ── PDF 1: ADA Claim Form — Patricia Nguyen ───────────────────────────────────
# CRITICAL: each label must be immediately followed by its value on the next line
# so the gold-layer regex r"Label\s*\n(value)" can match.

CLAIM_LINES = [
    "ADA DENTAL CLAIM FORM — ORIGINAL SUBMISSION",
    "Dearborn Group / HCSC | Commercial PPO",
    "Claim Reference: DG-2026-1001",
    "",
    "SECTION A — INSURED / SUBSCRIBER INFORMATION",
    "Subscriber Name",
    "Patricia Nguyen",
    "Subscriber ID",
    "HCSC-TX-88301124",
    "Date of Birth",
    "March 14, 1978",
    "Group Number",
    "GRP-MHS-2024-TX",
    "Plan Type",
    "Commercial PPO — HCSC PPO Silver TX",
    "Effective Date",
    "January 1, 2024",
    "",
    "SECTION B — PATIENT INFORMATION",
    "Patient Name",
    "Patricia Nguyen",
    "Relationship to Subscriber",
    "Self",
    "Secondary Coverage",
    "None",
    "",
    "SECTION C — TREATING PROVIDER",
    "Provider Name",
    "Dr. Sandra Okonkwo, DDS",
    "Practice",
    "Plano Family Dental Associates",
    "NPI Number",
    "1098765432",
    "Network Status",
    "In-Network PPO",
    "",
    "SECTION D — PROCEDURES PERFORMED",
    "Date of Service",
    "08/28/2026",
    "CDT Code",
    "D2740",
    "Description",
    "Crown porcelain ceramic substrate tooth 14",
    "Tooth Number",
    "14",
    "Billed Amount",
    "$1,450.00",
    "",
    "Date of Service",
    "08/28/2026",
    "CDT Code",
    "D0120",
    "Description",
    "Periodic oral evaluation",
    "Billed Amount",
    "$65.00",
    "",
    "Total Billed Amount",
    "$1,515.00",
    "",
    "Predetermination on File",
    "None",
    "",
    "SECTION E — CLINICAL REMARKS",
    "Tooth 14 presented with extensive decay. Full-coverage porcelain",
    "crown D2740 indicated. D0120 exam performed same visit.",
    "Radiograph report attached as supporting documentation.",
]

# ── PDF 2: Radiograph Report — Supporting Doc ─────────────────────────────────
# Must contain: periapical / bitewing / radiograph → xray_present = True
# The gold parser searches combined claim+proof text for these keywords.

PROOF_LINES = [
    "DENTAL RADIOGRAPH REPORT",
    "Dearborn Group / HCSC — Supporting Documentation",
    "Claim Reference: DG-2026-1001",
    "",
    "Patient Name: Patricia Nguyen",
    "Subscriber ID: HCSC-TX-88301124",
    "Date of Exam: August 14, 2026",
    "",
    "RADIOGRAPH FINDINGS",
    "",
    "Periapical X-ray — Tooth 14 (pre-treatment, August 14, 2026)",
    "  Extensive decay on mesial, occlusal, and distal surfaces of tooth 14.",
    "  Remaining tooth structure insufficient for inlay or onlay. Crown required.",
    "",
    "Bitewing X-ray — Posterior bitewings (August 14, 2026)",
    "  Confirms interproximal decay extent on tooth 14.",
    "  No pathology detected on adjacent teeth 13 or 15.",
    "",
    "RADIOGRAPH INTERPRETATION",
    "Radiograph evidence supports the clinical necessity of a full-coverage",
    "crown (D2740) on tooth 14. Both periapical and bitewing radiographs",
    "are provided per HCSC PPO Silver TX requirements for major restorative",
    "procedures.",
    "",
    "Interpreting Provider",
    "Dr. Sandra Okonkwo, DDS",
    "NPI: 1098765432",
    "Plano Family Dental Associates",
]


print("Generating test PDFs for Patricia Nguyen (expected result: APPROVED)...")
make_pdf(CLAIM_LINES, OUTPUT_DIR / "test_claim_patricia.pdf")
make_pdf(PROOF_LINES, OUTPUT_DIR / "test_proof_patricia_radiograph.pdf")

print()
print("Done. Upload these two files at http://localhost:5173")
print()
print("  Claim PDF  : ./backend/test_pdfs/test_claim_patricia.pdf")
print("  Proof PDF  : ./backend/test_pdfs/test_proof_patricia_radiograph.pdf")
print()
print("Expected Gold layer parse:")
print("  subscriber_id  = HCSC-TX-88301124")
print("  cdt_codes      = [D2740, D0120]")
print("  procedure_date = 08/28/2026")
print("  billed_amount  = 1515.0")
print("  xray_present   = True  (from proof PDF)")
print("  cob_flag       = False")
print("  predetermination_number = None")
print()
print("Expected Agent decision: APPROVED")
print("  D2740 ppo_allowed=$1180 x 50% coinsurance = $590.00")
print("  D0120 ppo_allowed=$45   x 50% coinsurance = $22.50")
