import os
import sqlite3
import requests
import hashlib
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "delta.db"
DOWNLOAD_DIR = os.path.join("output", "files")

DELTA_LOG_JSONL = os.path.join("output", "delta_records.jsonl")

# Define the path to the metadata records file, which contains the URLs to track
METADATA_RECORDS_JSONL = os.path.join("output", "metadata_records.jsonl")


def sha256_file(path):
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


def init_db():
    """Initialize the delta tracking database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Ensure all columns are present. If schema changes, you might need to
        # delete delta.db or add ALTER TABLE statements.
        c.execute("""
                  CREATE TABLE IF NOT EXISTS docs
                  (
                      url TEXT PRIMARY KEY,
                      last_modified TEXT,
                      checksum TEXT,
                      file_path TEXT,
                      last_checked TEXT
                  )
                  """)
        conn.commit()
        logger.info("Database initialized")
        return conn
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return None


def get_stored_urls():
    """Get all URLs currently stored in the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT url FROM docs")
        urls = [row[0] for row in c.fetchall()]
        conn.close()
        return urls
    except Exception as e:
        logger.error(f"Error getting stored URLs: {e}")
        return []


def extract_urls_from_records():
    """
    Extract download URLs from the metadata_records.jsonl file.
    This is the source of URLs that delta.py should track.
    """
    urls = set()

    # CRITICAL CHANGE: Read from METADATA_RECORDS_JSONL
    if os.path.exists(METADATA_RECORDS_JSONL):
        try:
            with open(METADATA_RECORDS_JSONL, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            # The 'download_url' key is what metadata.py outputs
                            download_url = record.get("download_url")
                            if download_url and download_url.startswith("http"):
                                urls.add(download_url)
                        except json.JSONDecodeError as e:
                            logger.error(f"Invalid JSON on line {line_num} in {METADATA_RECORDS_JSONL}: {e}")
        except Exception as e:
            logger.error(f"Error reading {METADATA_RECORDS_JSONL}: {e}")
    else:
        logger.warning(f"Metadata records file not found: {METADATA_RECORDS_JSONL}. No URLs to process.")


    logger.info(f"Found {len(urls)} URLs from existing metadata records")
    return list(urls)


def check_url_modified(url):
    """Check if a URL has been modified since last check"""
    try:
        # Use proper headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.head(url, headers=headers, timeout=30, allow_redirects=True)

        if response.status_code == 200:
            last_modified = response.headers.get("Last-Modified")
            content_length = response.headers.get("Content-Length")
            etag = response.headers.get("ETag")

            return {
                'last_modified': last_modified,
                'content_length': content_length,
                'etag': etag,
                'status': 'accessible'
            }
        else:
            logger.warning(f"URL returned status {response.status_code}: {url}")
            return {'status': 'inaccessible', 'status_code': response.status_code}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking URL {url}: {e}")
        return {'status': 'error', 'error': str(e)}


def process_url(url):
    """Process a single URL for delta checking"""
    conn = sqlite3.connect(DB_PATH) # Connect inside function to ensure fresh connection per URL
    if not conn:
        logger.error(f"Could not establish DB connection for URL: {url}")
        return

    try:
        c = conn.cursor()

        # Check current status of URL
        url_info = check_url_modified(url)

        if url_info['status'] != 'accessible':
            logger.warning(f"URL not accessible: {url} (Status: {url_info.get('status_code', 'N/A')})")
            # Update database with inaccessible status
            c.execute("""
                INSERT OR REPLACE INTO docs (url, last_checked, checksum, last_modified, file_path)
                VALUES (?, ?, ?, ?, ?)
            """, (url, datetime.utcnow().isoformat() + "Z", None, None, None))
            conn.commit()
            return

        # Get stored info
        c.execute("SELECT last_modified, checksum, file_path FROM docs WHERE url=?", (url,))
        row = c.fetchone()

        needs_download = False
        reason = ""

        if row:
            stored_lm, stored_checksum, stored_file_path = row
            current_lm = url_info.get('last_modified')

            if current_lm and stored_lm and current_lm != stored_lm:
                needs_download = True
                reason = "Last-Modified header changed"
            elif not current_lm: # If no Last-Modified header from server
                # Check if file exists and verify checksum
                if stored_file_path and os.path.exists(stored_file_path):
                    current_checksum = sha256_file(stored_file_path)
                    if current_checksum and current_checksum != stored_checksum: # Only compare if current_checksum is valid
                        needs_download = True
                        reason = "File checksum changed (no Last-Modified header)"
                else:
                    needs_download = True
                    reason = "Local file missing or path incorrect (no Last-Modified header)"
            elif not stored_lm and current_lm: # Server now provides Last-Modified, but we didn't have it before
                 needs_download = True
                 reason = "Server now provides Last-Modified header"
            # Else: Last-Modified matches or no Last-Modified and checksum/file status unchanged
        else:
            needs_download = True
            reason = "New URL (not in database)"

        if needs_download:
            logger.info(f"Downloading {url} - {reason}")

            # Download the file
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                response = requests.get(url, headers=headers, timeout=60, stream=True)
                response.raise_for_status()

                # Generate filename
                filename = os.path.basename(urlparse(url).path)
                if not filename or not filename.lower().endswith(('.pdf', '.epub')):
                    # Fallback to a hashed name if original filename is not suitable
                    filename = f"{hashlib.sha256(url.encode()).hexdigest()[:8]}.pdf" # Default to PDF if extension unknown

                file_path = os.path.join(DOWNLOAD_DIR, filename)

                # Ensure download directory exists
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)

                # Download with progress
                tmp_file_path = file_path + ".tmp"
                with open(tmp_file_path, "wb") as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                if downloaded == 0:
                    raise ValueError("Downloaded file is empty.")

                os.replace(tmp_file_path, file_path) # Atomically replace old file with new

                # Calculate new checksum
                new_checksum = sha256_file(file_path)

                # Update database
                c.execute("""
                    INSERT OR REPLACE INTO docs (url, last_modified, checksum, file_path, last_checked)
                    VALUES (?, ?, ?, ?, ?)
                """, (url, url_info.get('last_modified'), new_checksum, file_path, datetime.utcnow().isoformat() + "Z"))

                conn.commit()

                logger.info(f"Successfully downloaded: {url} -> {file_path} ({downloaded} bytes)")

            except Exception as e:
                logger.error(f"Error downloading {url}: {e}")
                # If download fails, update DB to reflect last_checked but no new file/checksum
                c.execute("""
                    INSERT OR REPLACE INTO docs (url, last_checked, checksum, last_modified, file_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (url, datetime.utcnow().isoformat() + "Z", stored_checksum if row else None, stored_lm if row else None, stored_file_path if row else None))
                conn.commit()
        else:
            logger.info(f"No changes detected for: {url}")

            # Update last checked time
            c.execute("""
                      UPDATE docs
                      SET last_checked = ?
                      WHERE url = ?
                      """, (datetime.utcnow().isoformat() + "Z", url))
            conn.commit()

    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
    finally:
        conn.close() # Ensure connection is closed


def process_all_urls():
    """Process all known URLs for delta checking"""
    # Get URLs from existing records (now correctly from metadata_records.jsonl)
    urls = extract_urls_from_records()

    if not urls:
        logger.warning("No URLs found to process for delta checking.")
        logger.info("Ensure the crawler and metadata extractor have run successfully to populate metadata_records.jsonl.")
        return

    logger.info(f"Processing {len(urls)} URLs for delta checking")

    for i, url in enumerate(urls, 1):
        logger.info(f"Processing URL {i}/{len(urls)}: {url}")
        process_url(url)

        # Small delay to be respectful to servers
        import time
        time.sleep(1)


def show_database_status():
    """Show current database status"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM docs")
        total_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM docs WHERE checksum IS NOT NULL")
        downloaded_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM docs WHERE last_checked IS NOT NULL")
        checked_count = c.fetchone()[0]

        logger.info(f"Database status:")
        logger.info(f"  Total URLs tracked: {total_count}")
        logger.info(f"  Successfully downloaded (at least once): {downloaded_count}")
        logger.info(f"  Last checked (any status): {checked_count}")

        # Show recent activity
        c.execute(
            "SELECT url, last_checked FROM docs WHERE last_checked IS NOT NULL ORDER BY last_checked DESC LIMIT 5")
        recent = c.fetchall()

        if recent:
            logger.info("Recent activity:")
            for url, last_checked in recent:
                logger.info(f"  {last_checked}: {url}")

        conn.close()

    except Exception as e:
        logger.error(f"Error showing database status: {e}")


def main():
    """Main function"""
    logger.info("Starting delta processing...")

    # Create download directory if it doesn't exist
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    # Ensure output directory for delta logs exists
    os.makedirs(os.path.dirname(DELTA_LOG_JSONL), exist_ok=True)

    # Initialize database
    conn = init_db()
    if not conn:
        logger.error("Could not initialize database")
        return
    conn.close() # Close the initial connection after init

    # Show current status
    show_database_status()

    # Process all URLs
    process_all_urls()

    # Show final status
    logger.info("Delta processing complete")
    show_database_status()


if __name__ == "__main__":
    main()
