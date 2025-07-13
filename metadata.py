import os
import json
import hashlib
import logging
from datetime import datetime
from urllib.parse import urlparse

# Try multiple PDF libraries for better compatibility
try:
    from PyPDF2 import PdfReader

    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    from pdfminer.pdfinterp import PDFResourceManager
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFPageInterpreter
    from io import StringIO

    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_JSONL = os.path.join("output", "records.jsonl")
os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)


def sha256_of_file(path):
    """Calculate SHA256 hash of a file"""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {path}: {e}")
        return None


def is_valid_pdf(path):
    """Check if file is a valid PDF by reading first few bytes"""
    try:
        with open(path, "rb") as f:
            first_bytes = f.read(10)
            return first_bytes.startswith(b'%PDF')
    except Exception:
        return False


def extract_pdf_metadata_pypdf2(path):
    """Extract metadata using PyPDF2"""
    try:
        reader = PdfReader(path)
        info = reader.metadata or {}

        title = str(info.get('/Title', '')) if info.get('/Title') else ''
        author = str(info.get('/Author', '')) if info.get('/Author') else ''

        # Try to extract creation date
        creation_date = info.get('/CreationDate')
        if creation_date:
            try:
                # PDF dates are in format: D:YYYYMMDDHHmmSSOHH'mm'
                date_str = str(creation_date)
                if date_str.startswith('D:'):
                    date_str = date_str[2:]
                if len(date_str) >= 8:
                    year = date_str[:4]
                    month = date_str[4:6] if len(date_str) >= 6 else '01'
                    day = date_str[6:8] if len(date_str) >= 8 else '01'
                    pub_year = f"{year}-{month}-{day}"
                else:
                    pub_year = None
            except Exception:
                pub_year = None
        else:
            pub_year = None

        return title, author, pub_year
    except Exception as e:
        logger.error(f"PyPDF2 failed for {path}: {e}")
        return None, None, None


def extract_pdf_metadata_pdfminer(path):
    """Extract metadata using pdfminer (more robust for problematic PDFs)"""
    try:
        # Try to extract some text to verify it's a readable PDF
        text = pdfminer_extract_text(path, maxpages=1)

        # For metadata, we'll use basic heuristics since pdfminer doesn't easily extract metadata
        filename = os.path.basename(path)
        title = filename.replace('.pdf', '').replace('_', ' ')

        return title, '', None
    except Exception as e:
        logger.error(f"PDFMiner failed for {path}: {e}")
        return None, None, None


def extract_pdf_metadata(path):
    """Extract metadata from PDF using available libraries"""
    if not os.path.exists(path):
        logger.error(f"File not found: {path}")
        return None, None, None

    if not is_valid_pdf(path):
        logger.error(f"Not a valid PDF file: {path}")
        return None, None, None

    # Try PyPDF2 first
    if HAS_PYPDF2:
        title, author, pub_year = extract_pdf_metadata_pypdf2(path)
        if title or author:  # If we got some metadata
            return title, author, pub_year

    # Fallback to pdfminer
    if HAS_PDFMINER:
        title, author, pub_year = extract_pdf_metadata_pdfminer(path)
        if title:
            return title, author, pub_year

    # Last resort: use filename
    filename = os.path.basename(path)
    title = filename.replace('.pdf', '').replace('_', ' ')
    logger.warning(f"Using filename as title for {path}")

    return title, '', None


def build_record(file_path, source_url=None):
    """Build a metadata record for a file"""
    try:
        # Basic file info
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        logger.info(f"Processing: {filename} ({file_size} bytes)")

        # Skip if file is too small (likely an error page)
        if file_size < 1024:
            logger.warning(f"File too small, skipping: {filename}")
            return None

        # Calculate checksum
        checksum = sha256_of_file(file_path)
        if not checksum:
            logger.error(f"Could not calculate checksum for {filename}")
            return None

        # Extract metadata
        title, author, pub_year = extract_pdf_metadata(file_path)

        # Use filename as fallback title
        if not title:
            title = filename.replace('.pdf', '').replace('_', ' ')

        # Use file modification time as fallback date
        if not pub_year:
            try:
                file_mtime = os.path.getmtime(file_path)
                pub_year = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d')
            except Exception:
                pub_year = datetime.now().strftime('%Y-%m-%d')

        # Determine source domain
        if source_url:
            domain = urlparse(source_url).netloc
        else:
            domain = "local"

        # Build record
        record = {
            "site": domain,
            "document_id": os.path.splitext(filename)[0],
            "title": title or filename,
            "authors": [author] if author else [],
            "pub_year": pub_year,
            "language": "Sanskrit",  # Default for this project
            "download_url": source_url or f"file://{file_path}",
            "checksum": checksum,
            "file_size": file_size,
            "scraped_at": datetime.utcnow().isoformat() + "Z"
        }

        return record

    except Exception as e:
        logger.error(f"Error building record for {file_path}: {e}")
        return None


def append_record(record):
    """Append a record to the JSONL file"""
    if not record:
        return

    try:
        with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"Recorded: {record['document_id']}")
    except Exception as e:
        logger.error(f"Error writing record: {e}")


def process_all_files():
    """Process all files in the download directory"""
    files_dir = os.path.join("output", "files")

    if not os.path.exists(files_dir):
        logger.error(f"Directory not found: {files_dir}")
        return

    files = os.listdir(files_dir)
    pdf_files = [f for f in files if f.lower().endswith('.pdf')]

    logger.info(f"Found {len(pdf_files)} PDF files to process")

    successful = 0
    failed = 0

    for filename in pdf_files:
        file_path = os.path.join(files_dir, filename)
        try:
            record = build_record(file_path)
            if record:
                append_record(record)
                successful += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            failed += 1

    logger.info(f"Processing complete. Successful: {successful}, Failed: {failed}")


if __name__ == "__main__":
    logger.info("Starting metadata extraction...")
    process_all_files()
    logger.info("Metadata extraction complete.")