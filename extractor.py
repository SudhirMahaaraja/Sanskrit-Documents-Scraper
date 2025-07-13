import os
import json
import logging
from typing import Optional, List

from PIL import Image, ImageFilter, ImageEnhance

# ─── Dependencies ──────────────────────────────────────────────────────────────
HAS_OCR = False
HAS_PDFMINER = False
HAS_PYPDF2 = False

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text

    HAS_PDFMINER = True
except ImportError:
    logging.warning("PDFMiner not installed. Text extraction from native PDFs might be limited.")

try:
    from PyPDF2 import PdfReader

    HAS_PYPDF2 = True
except ImportError:
    logging.warning("PyPDF2 not installed. Text extraction from native PDFs might be limited.")

try:
    import pytesseract
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError

    # Configure Tesseract path - IMPORTANT for Windows
    pytesseract.pytesseract.tesseract_cmd = os.environ.get(
        "TESSERACT_PATH",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Default path for Windows
    )

    # Verify Poppler path - IMPORTANT for Windows and Linux
    POPPLER_PATH = os.environ.get(
        "POPPLER_PATH",
        r"C:\Program Files\poppler-24.08.0\Library\bin"  # Default path for Windows
    )
    if not os.path.isdir(POPPLER_PATH):
        logging.warning(
            f"Poppler path not found at '{POPPLER_PATH}'. OCR will not work for PDFs. Set POPPLER_PATH environment variable.")
        HAS_OCR = False
    else:
        HAS_OCR = True

except ImportError as e:
    logging.warning(
        f"OCR dependencies (pytesseract or pdf2image) not installed: {e}. OCR functionality will be disabled.")
    HAS_OCR = False
except Exception as e:
    logging.warning(f"Error during OCR setup: {e}. OCR functionality will be disabled.")
    HAS_OCR = False

# ─── Logging & Paths ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OUTPUT_JSONL = os.path.join("output", "records.jsonl")
FILES_DIR = os.path.join("output", "files")

# --- OCR Configuration ---
# Crucial: Specify all languages present in your PDFs.
# You MUST have 'eng.traineddata', 'hin.traineddata', and 'san.traineddata'
# installed in your Tesseract tessdata directory for this to work.
OCR_LANGUAGES = "eng+hin+san"
# Further Tesseract configurations can be added here
# --oem 3: Use LSTM engine (recommended for better accuracy)
# --psm 3: Default, automatic page segmentation. Good general purpose.
# Consider psm 6 (assume a single uniform block of text) if psm 3 is poor for paragraphs.
OCR_CONFIG = r"--oem 3 --psm 3"
# Define a maximum number of pages to OCR. Large PDFs can be very slow.
# Set to None to process all pages (can be very slow for 700+ pages).
# Set a number (e.g., 50) if you only need the first part or have performance constraints.
MAX_OCR_PAGES = None  # Set to None for all pages, or an integer like 50


# ─── Extraction Methods ────────────────────────────────────────────────────────
def extract_text_pdfminer(pdf_path: str) -> Optional[str]:
    """Extracts text using PDFMiner."""
    logger.info("  [PDFMiner] trying...")
    if not HAS_PDFMINER:
        logger.info("  [PDFMiner] PDFMiner not available.")
        return None
    try:
        text = pdfminer_extract_text(pdf_path)
        return text.strip() or None
    except Exception as e:
        logger.info(f"  [PDFMiner] failed: {e}")
        return None


def extract_text_pypdf2(pdf_path: str) -> Optional[str]:
    """Extracts text using PyPDF2."""
    logger.info("  [PyPDF2] trying...")
    if not HAS_PYPDF2:
        logger.info("  [PyPDF2] PyPDF2 not available.")
        return None
    try:
        reader = PdfReader(pdf_path)
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n".join(pages).strip()
        return text or None
    except Exception as e:
        logger.info(f"  [PyPDF2] failed: {e}")
        return None


def preprocess_image(img: Image.Image) -> Image.Image:
    """
    Preprocesses an image for OCR to improve accuracy, especially for scanned documents.
    Steps include: grayscale, enhancing contrast/sharpness, noise reduction, and binarization.
    """
    # 1. Convert to grayscale
    gray = img.convert("L")

    # 2. Enhance Contrast and Sharpness
    # These steps can make text stand out more, crucial for scanned documents
    enhancer = ImageEnhance.Contrast(gray)
    contrasted = enhancer.enhance(1.5)  # Increase contrast by 50%

    enhancer = ImageEnhance.Sharpness(contrasted)
    sharpened = enhancer.enhance(2.0)  # Increase sharpness by 100%

    # 3. Apply Median Filter to reduce noise (after contrast/sharpness)
    # Median filter is good for salt-and-pepper noise without blurring edges too much.
    filtered = sharpened.filter(ImageFilter.MedianFilter(size=3))  # Size 3 or 5 often works well

    # 4. Binarize using an adaptive approach or a carefully chosen threshold.
    # Simple fixed threshold (128) might be too harsh for some documents.
    # For more robust binarization, especially for varying document qualities,
    # consider using libraries like OpenCV for Otsu's binarization or adaptive thresholding.
    # PIL's 'point' method can approximate a form of adaptive thresholding by analyzing pixel distribution.
    # However, for simplicity and common OCR cases, a slightly tuned fixed threshold can work.

    # Let's try a slightly different binarization approach:
    # Binarize (convert to pure black and white) - pixels below 150 become black, above 150 become white
    # This value might need tuning based on document type. A lower value keeps more dark pixels.
    bw = filtered.point(lambda x: 0 if x < 150 else 255, "1")

    # Another common preprocessing step: Dilation/Erosion (morphological operations)
    # Can make thin text thicker or remove small noise, but requires OpenCV or similar.
    # e.g., from cv2 import erode, dilate, getStructuringElement, MORPH_RECT
    # kernel = getStructuringElement(MORPH_RECT, (2,2))
    # bw_np = np.array(bw)
    # bw_dilated = dilate(bw_np, kernel, iterations = 1)
    # bw = Image.fromarray(bw_dilated)

    return bw


def extract_text_ocr(pdf_path: str, max_pages: int = MAX_OCR_PAGES) -> Optional[str]:
    """
    Extracts text from PDF using OCR (Tesseract).
    Processes all pages by default or up to max_pages if specified.
    """
    if not HAS_OCR:
        logger.info("  [OCR] OCR dependencies (pytesseract/pdf2image/Poppler) not available or configured.")
        return None

    logger.info(
        f"  [OCR] converting pages at 300dpi for OCR (up to {max_pages if max_pages is not None else 'all'} pages)...")

    try:
        pages = convert_from_path(
            pdf_path,
            dpi=300,  # High DPI for better OCR accuracy
            first_page=1,
            last_page=max_pages,  # Will be None if MAX_OCR_PAGES is None
            poppler_path=POPPLER_PATH
        )
    except PDFInfoNotInstalledError:
        logger.error(
            "  [OCR] Poppler is not installed or not found in PATH. Please install Poppler and set POPPLER_PATH environment variable.")
        return None
    except PDFPageCountError:
        logger.error("  [OCR] Could not determine the number of pages in the PDF. It might be corrupted.")
        return None
    except Exception as e:
        logger.info(f"  [OCR] convert_from_path failed: {e}")
        return None

    logger.info(f"  [OCR] {len(pages)} image(s) generated, preprocessing + OCR...")
    ocr_texts = []

    for idx, img in enumerate(pages, start=1):
        logger.info(f"    page {idx}: original size {img.size}, mode {img.mode}")

        # Consider increasing DPI for very dense or low-quality text.
        # If 300 DPI images are still blurry or text is too small, try 400 or 600 DPI.
        # This increases processing time and memory significantly.
        # Example: img = convert_from_path(pdf_path, dpi=400, first_page=idx, last_page=idx, poppler_path=POPPLER_PATH)[0]

        proc = preprocess_image(img)
        logger.info(f"    page {idx}: after preprocess mode={proc.mode}, size={proc.size}")

        try:
            # Use the defined OCR_LANGUAGES and OCR_CONFIG
            txt = pytesseract.image_to_string(proc, lang=OCR_LANGUAGES, config=OCR_CONFIG, timeout=120).strip()
            logger.info(f"    page {idx}: OCR extracted {len(txt)} chars")
            if txt:
                ocr_texts.append(txt)
            else:
                logger.info(
                    f"    page {idx}: OCR extracted no text after preprocessing. Consider adjusting preprocessing or OCR config.")
        except pytesseract.TesseractError as e:
            logger.error(
                f"    page {idx}: Tesseract OCR failed (error code/message): {e}. This often means a language pack is missing or invalid config.")
        except Exception as e:
            logger.info(f"    page {idx}: OCR failed for unexpected reason: {e}")

    return "\n".join(ocr_texts) or None


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Attempts to extract text from a PDF using multiple methods:
    1. PDFMiner (for native text)
    2. PyPDF2 (for native text)
    3. OCR (for scanned/image-based PDFs)
    """

    # 1) PDFMiner (best for native text)
    txt = extract_text_pdfminer(pdf_path)
    if txt:
        logger.info("  [Success] Text extracted using PDFMiner.")
        return txt

    # 2) PyPDF2 (alternative for native text)
    txt = extract_text_pypdf2(pdf_path)
    if txt:
        logger.info("  [Success] Text extracted using PyPDF2.")
        return txt

    # 3) OCR (fallback for image-based PDFs)
    txt = extract_text_ocr(pdf_path)
    if txt:
        logger.info("  [Success] Text extracted using OCR.")
        return txt
    else:
        logger.warning("  [Warning] No text extracted by any method for this PDF.")

    return ""  # no text found


# ─── Orchestration ────────────────────────────────────────────────────────────
def find_all_pdfs() -> List[str]:
    """Finds all PDF files in the configured FILES_DIR."""
    if not os.path.isdir(FILES_DIR):
        logger.error("Files directory '%s' does not exist.", FILES_DIR)
        return []
    pdfs = [
        os.path.join(FILES_DIR, f)
        for f in os.listdir(FILES_DIR)
        if f.lower().endswith(".pdf")
    ]
    if not pdfs:
        logger.warning("No PDFs found in '%s'.", FILES_DIR)
    return pdfs


def save_records(records: List[dict]):
    """Saves extracted records to a JSONL file."""
    os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Records saved to '%s'.", OUTPUT_JSONL)


def main():
    """Main function to orchestrate PDF text extraction."""
    logger.info("Starting PDF text extraction process...")

    # Initial checks for OCR dependencies
    if HAS_OCR:
        logger.info(f"OCR (pytesseract, pdf2image, Poppler) is configured and available. Languages: {OCR_LANGUAGES}")
        if MAX_OCR_PAGES is not None:
            logger.info(f"OCR will process a maximum of {MAX_OCR_PAGES} pages per PDF.")
        else:
            logger.info("OCR will process all pages per PDF (can be slow for very large documents).")
    else:
        logger.warning(
            "OCR will not be used. Please ensure pytesseract, pdf2image, and Poppler are correctly installed and configured if you need OCR for scanned PDFs.")

    pdfs = find_all_pdfs()
    if not pdfs:
        return

    records = []
    for pdf_path in pdfs:
        doc_id = os.path.splitext(os.path.basename(pdf_path))[0]
        logger.info(f"\n--- Processing: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)

        if text:
            # Adjust snippet to show more context if text is available
            snippet = text.replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            logger.info("Extracted (snippet): %s", snippet)
        else:
            logger.info("Extracted text: <none>")

        records.append({
            "document_id": doc_id,
            "content": text,
            "content_length": len(text)
        })

    save_records(records)
    logger.info("\nFinished. %d documents processed.", len(records))


if __name__ == "__main__":
    main()