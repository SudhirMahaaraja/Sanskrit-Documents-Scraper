
import os
import logging
from crawler import Crawler, TARGET_SITES, DOWNLOAD_DIR
from metadata import build_record, append_record
from extractor import attach_content
from delta import init_db, process_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def run_delta(sites):
    """
    Perform delta processing on each target site URL to
    only fetch changed or new documents.
    """
    logger.info("Starting delta processing...")
    conn = init_db()
    for url in sites:
        try:
            process_url(url)
        except Exception as e:
            logger.error(f"Delta failed for {url}: {e}")
    logger.info("Delta processing complete.")


def run_crawler(sites):
    """
    Crawl and download documents from each target site.
    """
    logger.info("Starting crawler...")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    for site in sites:
        logger.info(f"Crawling: {site}")
        try:
            Crawler(site).crawl()
        except Exception as e:
            logger.error(f"Crawler error for {site}: {e}")
    logger.info("Crawling complete.")


def run_metadata():
    """
    Extract metadata from downloaded files and append to JSONL.
    """
    logger.info("Starting metadata extraction...")
    files = os.listdir(DOWNLOAD_DIR)
    for fname in files:
        path = os.path.join(DOWNLOAD_DIR, fname)
        try:
            rec = build_record(path, source_url="file://" + path)
            append_record(rec)
            logger.info(f"Metadata recorded for {fname}")
        except Exception as e:
            logger.error(f"Metadata extraction failed for {fname}: {e}")
    logger.info("Metadata extraction complete.")


def run_extractor():
    """
    Attach text content (embedded or via OCR) to JSON records.
    """
    logger.info("Starting text extraction & OCR...")
    try:
        attach_content()
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
    logger.info("Text extraction complete.")


def main():
    """Main entry point"""
    # 1) Delta (optional)
    run_delta(TARGET_SITES)

    # 2) Crawl & download
    run_crawler(TARGET_SITES)

    # 3) Metadata extraction
    run_metadata()

    # 4) Text extraction & OCR
    run_extractor()

    logger.info("All steps completed successfully.")


if __name__ == "__main__":
    main()
