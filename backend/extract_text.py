"""
PDF text extraction utility used by the medallion pipeline.
Tries native text extraction first; falls back to Tesseract OCR if the page has no embedded text.
"""
import fitz  # PyMuPDF
from pathlib import Path


def extract_pdf_to_string(pdf_path: str) -> tuple[str, str]:
    """
    Extract all text from a PDF file.
    Returns (full_text, method) where method is "normal" or "ocr".
    """
    doc = fitz.open(Path(pdf_path))
    pages = []
    method = "normal"

    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text)
        else:
            method = "ocr"
            try:
                tp = page.get_textpage_ocr(language="eng", dpi=300)
                ocr_text = page.get_text("text", textpage=tp)
                pages.append(ocr_text if ocr_text.strip() else "[NO TEXT]")
            except Exception:
                pages.append("[OCR FAILED]")

    doc.close()
    return "\n".join(pages), method
