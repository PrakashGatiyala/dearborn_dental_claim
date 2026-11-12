"""Quick smoke-test: parse the test PDFs through the same logic as medallion.py."""
import re
import json
from extract_text import extract_pdf_to_string

claim_text, m1 = extract_pdf_to_string("/app/test_pdfs/test_claim_patricia.pdf")
proof_text, m2 = extract_pdf_to_string("/app/test_pdfs/test_proof_patricia_radiograph.pdf")
combined = claim_text + "\n" + proof_text


def _first(pat, text, flags=0):
    m = re.search(pat, text, flags)
    return m.group(1).strip() if m else None


subscriber_id = _first(r"Subscriber ID\s*\n([A-Z]+-[A-Z]+-\d+)", claim_text)
cdt_codes = list(dict.fromkeys(re.findall(r"\b(D\d{4})\b", claim_text)))
dos_raw = _first(r"Date of Service\s*\n(\d{2}/\d{2}/\d{4})", claim_text)
npi = _first(r"NPI Number\s*\n(\d{10})", claim_text)
provider = _first(r"Provider Name\s*\n(.+)", claim_text)
amounts = re.findall(r"\$[\d,]+\.?\d*", claim_text)
billed = max(float(a.replace("$", "").replace(",", "")) for a in amounts) if amounts else None
predet = _first(r"(PDET[-\d]+)", combined)
xray = bool(re.search(r"(?i)(x.?ray|radiograph|bitewing|periapical)", combined))
cob_raw = _first(r"Secondary Coverage\s*\n(.+)", claim_text)
cob_flag = bool(cob_raw and cob_raw.strip().lower() not in ("none", "n/a", ""))

result = {
    "extraction_method_claim": m1,
    "extraction_method_proof": m2,
    "subscriber_id": subscriber_id,
    "cdt_codes": cdt_codes,
    "procedure_date": dos_raw,
    "billed_amount": billed,
    "provider_npi": npi,
    "provider_name": provider,
    "predetermination_number": predet,
    "xray_present": xray,
    "cob_flag": cob_flag,
}
print(json.dumps(result, indent=2))

# Assert all critical fields parsed
assert subscriber_id == "HCSC-TX-88301124", f"subscriber_id mismatch: {subscriber_id}"
assert "D2740" in cdt_codes, f"D2740 missing from cdt_codes: {cdt_codes}"
assert "D0120" in cdt_codes, f"D0120 missing from cdt_codes: {cdt_codes}"
assert dos_raw == "08/28/2026", f"procedure_date mismatch: {dos_raw}"
assert billed == 1515.0, f"billed_amount mismatch: {billed}"
assert npi == "1098765432", f"NPI mismatch: {npi}"
assert provider and "Okonkwo" in provider, f"provider_name mismatch: {provider}"
assert xray is True, "xray_present should be True"
assert cob_flag is False, "cob_flag should be False"
assert predet is None, f"predetermination_number should be None: {predet}"

print("\nAll assertions passed — PDFs will parse correctly through the medallion pipeline.")
