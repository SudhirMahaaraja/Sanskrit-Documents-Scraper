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

METADATA_JSONL = os.path.join("output", "metadata_records.jsonl")
CRAWLING_RECORDS_JSON = os.path.join("output", "crawling_records.json")

os.makedirs(os.path.dirname(METADATA_JSONL), exist_ok=True)
os.makedirs(os.path.dirname(CRAWLING_RECORDS_JSON), exist_ok=True)


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


def build_metadata_record(file_path, crawling_info):
    """
    Build a metadata record for a file using extracted PDF metadata
    and crawling information.
    """
    try:
        # Basic file info
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        logger.info(f"Building metadata for: {filename} ({file_size} bytes)")

        # Skip if file is too small (likely an error page)
        if file_size < 1024:
            logger.warning(f"File too small, skipping metadata for: {filename}")
            return None

        # Calculate checksum
        checksum = sha256_of_file(file_path)
        if not checksum:
            logger.error(f"Could not calculate checksum for {filename}, skipping metadata.")
            return None

        # Extract metadata from PDF (author, pub_year, title)
        title, author, pub_year = extract_pdf_metadata(file_path)

        # Use filename as fallback title if not extracted from PDF
        if not title:
            title = filename.replace('.pdf', '').replace('_', ' ')

        # Use file modification time as fallback date if not extracted from PDF
        if not pub_year:
            try:
                file_mtime = os.path.getmtime(file_path)
                pub_year = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d')
            except Exception:
                pub_year = datetime.now().strftime('%Y-%m-%d')

        # Get download_url and site from crawling_info
        download_url = crawling_info.get('original_download_url')
        if download_url:
            domain = urlparse(download_url).netloc
        else:
            domain = "local"  # Fallback if URL is missing in crawling info
            download_url = f"file://{os.path.abspath(file_path)}"  # Default to local file URL

        # Build metadata record
        record = {
            "site": domain,
            "document_id": os.path.splitext(filename)[0],
            "title": title or filename,
            "authors": [author] if author else [],
            "pub_year": pub_year,
            "language": "Sanskrit",  # Default for this project
            "download_url": download_url,
            "checksum": checksum,
            "file_size": file_size,
            "scraped_at": datetime.utcnow().isoformat() + "Z"
        }

        return record

    except Exception as e:
        logger.error(f"Error building metadata record for {file_path}: {e}")
        return None


def append_metadata_record(record):
    """Append a metadata record to the JSONL file"""
    if not record:
        return

    try:
        with open(METADATA_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"Appended metadata for: {record['document_id']}")
    except Exception as e:
        logger.error(f"Error writing metadata record: {e}")


def load_crawling_records_map():
    """
    Load crawling records from crawling_records.json and return a dictionary
    mapping local file paths to their crawling information.
    """
    crawling_data_map = {}
    if os.path.exists(CRAWLING_RECORDS_JSON) and os.path.getsize(CRAWLING_RECORDS_JSON) > 0:
        try:
            with open(CRAWLING_RECORDS_JSON, "r", encoding="utf-8") as f:
                records = json.load(f)
                for record in records:
                    if 'local_file_path' in record:
                        # Normalize path to ensure consistent lookup, relative to current working dir
                        normalized_local_path = os.path.normpath(record['local_file_path'])
                        crawling_data_map[normalized_local_path] = record
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding {CRAWLING_RECORDS_JSON}: {e}. File might be corrupted or empty.")
        except Exception as e:
            logger.error(f"Error loading crawling records: {e}")
    else:
        logger.warning(f"Crawling records file not found or empty: {CRAWLING_RECORDS_JSON}")
    return crawling_data_map


def process_all_files():
    """Process all files in the download directory"""
    files_dir = os.path.join("output", "files")

    if not os.path.exists(files_dir):
        logger.error(f"Directory not found: {files_dir}")
        return

    # Load crawling records to get source URLs and other crawling info
    crawling_records_map = load_crawling_records_map()
    logger.info(f"Loaded {len(crawling_records_map)} crawling records for lookup.")

    pdf_files_in_dir = [f for f in os.listdir(files_dir) if f.lower().endswith('.pdf')]

    logger.info(f"Found {len(pdf_files_in_dir)} PDF files to process for metadata extraction.")

    successful_metadata = 0
    failed = 0

    for filename in pdf_files_in_dir:
        file_path = os.path.join(files_dir, filename)

        # Normalize the file_path to match how it might be stored in crawling_records.json
        # E.g., if crawling_records.json stores "output/files/my_doc.pdf"
        normalized_current_file_path = os.path.normpath(file_path)

        crawling_info = crawling_records_map.get(normalized_current_file_path)

        if not crawling_info:
            logger.warning(
                f"No crawling record found for {filename} at path {normalized_current_file_path}. Skipping metadata generation for this file.")
            failed += 1
            continue

        try:
            record = build_metadata_record(file_path, crawling_info)
            if record:
                append_metadata_record(record)
                successful_metadata += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            failed += 1

    logger.info(f"Processing complete. Successful metadata records: {successful_metadata}, Failed: {failed}")


if __name__ == "__main__":
    logger.info("Starting metadata extraction from PDF files using crawling records...")
    process_all_files()
    logger.info("Metadata extraction complete.")