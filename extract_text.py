
import fitz  # PyMuPDF
import sys
from pathlib import Path


def extract_text_from_pdf(pdf_path):
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)

    print("=" * 80)
    print(f"PDF: {pdf_path.name}")
    print(f"Total Pages: {len(doc)}")
    print("=" * 80)

    all_text = []

    for page_number, page in enumerate(doc, start=1):

        print(f"\n{'=' * 30} PAGE {page_number} {'=' * 30}\n")

        # ---------------------------------------------------------
        # STEP 1: Try normal PDF text extraction
        # ---------------------------------------------------------
        normal_text = page.get_text("text")

        if normal_text.strip():
            print(">>> NORMAL PDF TEXT EXTRACTION\n")
            print(normal_text)

            all_text.append(
                f"\n{'=' * 30} PAGE {page_number} - NORMAL TEXT {'=' * 30}\n"
                f"{normal_text}"
            )

        else:
            print(">>> NO NORMAL TEXT FOUND")
            print(">>> Trying OCR...\n")

            # -----------------------------------------------------
            # STEP 2: OCR using Tesseract through PyMuPDF
            # -----------------------------------------------------

            try:
                text_page = page.get_textpage_ocr(
                    language="eng",
                    dpi=300
                )

                # Convert TextPage object into actual text
                ocr_text = page.get_text(
                    "text",
                    textpage=text_page
                )

                if ocr_text.strip():
                    print(">>> OCR TEXT\n")
                    print(ocr_text)

                    all_text.append(
                        f"\n{'=' * 30} PAGE {page_number} - OCR {'=' * 30}\n"
                        f"{ocr_text}"
                    )

                else:
                    print("[NO TEXT FOUND EVEN AFTER OCR]")

                    all_text.append(
                        f"\n{'=' * 30} PAGE {page_number} {'=' * 30}\n"
                        "[NO TEXT FOUND EVEN AFTER OCR]"
                    )

            except Exception as e:
                print(f"❌ OCR failed: {e}")

                all_text.append(
                    f"\n{'=' * 30} PAGE {page_number} {'=' * 30}\n"
                    f"OCR ERROR: {e}"
                )

    # -------------------------------------------------------------
    # Save extracted text
    # -------------------------------------------------------------

    output_file = pdf_path.with_suffix(".txt")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_text))

    doc.close()

    print("\n" + "=" * 80)
    print("✅ Extraction completed")
    print(f"📄 Output saved to: {output_file}")
    print("=" * 80)


def extract_pdf_to_string(pdf_path: str) -> tuple[str, str]:
    """
    Importable wrapper used by the medallion pipeline.
    Returns (full_text, method) where method is "normal" or "ocr".
    """
    import fitz
    from pathlib import Path

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


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage:")
        print("python extract_text.py <path_to_pdf>")
        print()
        print("Example:")
        print(
            'python extract_text.py '
            '"C:\\Users\\Lavanya\\Documents\\sample.pdf"'
        )
        sys.exit(1)

    pdf_file = sys.argv[1]

    extract_text_from_pdf(pdf_file)

