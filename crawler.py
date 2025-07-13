import os
import time
import hashlib
import requests
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Increased timeouts and better user agent
REQUEST_TIMEOUT = (15, 60)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

TARGET_SITES = [
    "https://sanskritdocuments.org/scannedbooks/asisanskritpdfs.html",
    "https://sanskritdocuments.org/scannedbooks/asiallpdfs.html",
    "https://indianculture.gov.in/ebooks",
    "https://ignca.gov.in/divisionss/asi-books/",
    "https://archive.org/details/TFIC_ASI_Books/ACatalogueOfTheSamskritManuscriptsInTheAdyarLibraryPt.1/",
    "https://indianmanuscripts.com/",
    "https://niimh.nic.in/ebooks/ayuhandbook/index.php",
]

DOWNLOAD_DIR = os.path.join("output", "files")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class Crawler:
    def __init__(self, base_url):
        self.base_url = base_url
        self.visited = set()
        self.session = requests.Session()

        # Set up session with better headers
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Handle robots.txt
        rp = RobotFileParser()
        rp.set_url(urljoin(base_url, "/robots.txt"))
        try:
            rp.read()
        except Exception as e:
            logger.warning(f"Could not read robots.txt for {base_url}: {e}")
        self.robots = rp

    def crawl(self, url=None):
        url = url or self.base_url
        if url in self.visited:
            return
        self.visited.add(url)

        if self.robots.can_fetch("*", url) is False:
            logger.info(f"Robots.txt disallows crawling: {url}")
            return

        try:
            logger.info(f"Fetching: {url}")
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
            resp.raise_for_status()  # Raise exception for bad status codes
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return

        content_type = resp.headers.get("Content-Type", "").lower()
        content_length = resp.headers.get("Content-Length")

        # Check if it's a PDF or EPUB
        is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")
        is_epub = "epub" in content_type or url.lower().endswith(".epub")

        if is_pdf or is_epub:
            logger.info(f"Found document: {url} (Content-Type: {content_type})")
            self._download_file(url, resp)
            return

        # If it's HTML, parse and continue crawling
        if "text/html" in content_type:
            try:
                html = resp.content
                soup = BeautifulSoup(html, "html.parser")
                self._process_html_page(url, soup)
            except Exception as e:
                logger.error(f"Error parsing HTML at {url}: {e}")
                return
        else:
            logger.info(f"Skipping non-HTML content: {url} (Content-Type: {content_type})")

    def _process_html_page(self, url, soup):
        """Process HTML page and extract links"""
        # Rate limiting
        time.sleep(2)  # Increased delay to be more respectful

        # Look for PDF/EPUB links
        document_links = []
        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            if not href:
                continue

            # Remove fragments
            href = href.split('#')[0]
            full_url = urljoin(url, href)

            # Check if it's a document link
            if (full_url.lower().endswith(('.pdf', '.epub')) or
                    'pdf' in href.lower() or 'epub' in href.lower()):
                document_links.append(full_url)
            elif self._is_internal(full_url) and full_url not in self.visited:
                # Queue for further crawling
                self.crawl(full_url)

        # Process document links
        for doc_url in document_links:
            if doc_url not in self.visited:
                self.crawl(doc_url)

    def _download_file(self, file_url, response=None):
        """Download a file with better error handling"""
        try:
            # Generate a stable filename
            fname_hash = hashlib.sha256(file_url.encode('utf-8')).hexdigest()[:8]
            path = urlparse(file_url).path
            basename = os.path.basename(path)
            if not basename or not os.path.splitext(basename)[1]:
                # Try to get extension from URL or content type
                if file_url.lower().endswith('.pdf'):
                    basename = "document.pdf"
                elif file_url.lower().endswith('.epub'):
                    basename = "document.epub"
                else:
                    basename = "document.pdf"  # Default assumption

            local_name = f"{fname_hash}_{basename}"
            local_path = os.path.join(DOWNLOAD_DIR, local_name)

            # If we don't have a response object, fetch the file
            if response is None:
                logger.info(f"Downloading: {file_url}")
                response = self.session.get(file_url, timeout=REQUEST_TIMEOUT, stream=True)
                response.raise_for_status()

            # Check content length
            content_length = response.headers.get("Content-Length")
            if content_length:
                content_length = int(content_length)
                if content_length < 1024:  # Less than 1KB might be an error page
                    logger.warning(f"File seems too small ({content_length} bytes): {file_url}")
                    # Still try to download, but warn

            # Skip if already downloaded and same size
            if os.path.exists(local_path) and content_length:
                if os.path.getsize(local_path) == content_length:
                    logger.info(f"Already downloaded: {local_name}")
                    return

            # Download the file
            temp_path = local_path + ".tmp"
            try:
                with open(temp_path, "wb") as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                    logger.info(f"Downloaded {downloaded} bytes")

                # Verify the download
                if downloaded == 0:
                    logger.error(f"Downloaded file is empty: {file_url}")
                    os.remove(temp_path)
                    return

                # Check if it's actually a PDF by reading first few bytes
                with open(temp_path, "rb") as f:
                    first_bytes = f.read(10)
                    if basename.endswith('.pdf') and not first_bytes.startswith(b'%PDF'):
                        logger.warning(f"Downloaded file doesn't appear to be a valid PDF: {file_url}")
                        # Save anyway, but log the warning

                # Move temp file to final location
                os.rename(temp_path, local_path)
                logger.info(f"Successfully downloaded: {file_url} → {local_name}")

            except Exception as e:
                logger.error(f"Error during download: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise

        except requests.exceptions.HTTPError as e:
            if response and response.status_code == 403:
                logger.error(f"Access forbidden (403) for: {file_url}")
                logger.info("This might be due to:")
                logger.info("1. Server blocking automated requests")
                logger.info("2. Authentication required")
                logger.info("3. Rate limiting")
                logger.info("4. Referrer checking")
            else:
                logger.error(f"HTTP error {e} for: {file_url}")
        except Exception as e:
            logger.error(f"Unexpected error downloading {file_url}: {e}")

    def _is_internal(self, url):
        """Check if URL is internal to the base domain"""
        base_domain = urlparse(self.base_url).netloc
        url_domain = urlparse(url).netloc
        return url_domain == base_domain or url_domain.endswith('.' + base_domain)


def test_url_accessibility(url):
    """Test if a URL is accessible before crawling"""
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT})
        resp = session.head(url, timeout=REQUEST_TIMEOUT)
        logger.info(f"URL {url} returned status: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Cannot access {url}: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting Sanskrit Documents Crawler")

    for site in TARGET_SITES:
        logger.info(f"Testing accessibility of: {site}")
        if test_url_accessibility(site):
            logger.info(f"Starting crawl: {site}")
            try:
                crawler = Crawler(site)
                crawler.crawl()
            except Exception as e:
                logger.error(f"Crawler failed for {site}: {e}")
        else:
            logger.warning(f"Skipping inaccessible site: {site}")

    logger.info("Crawling completed")