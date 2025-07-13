import os
import time
import json
import hashlib
import requests
from datetime import datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Timeouts and user agent
REQUEST_TIMEOUT = (15, 60)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)

# List of sites to crawl
TARGET_SITES = [
    "https://sanskritdocuments.org/scannedbooks/asisanskritpdfs.html",
    "https://sanskritdocuments.org/scannedbooks/asiallpdfs.html",
    "https://indianculture.gov.in/ebooks",
    "https://ignca.gov.in/divisionss/asi-books/",
    "https://archive.org/details/TFIC_ASI_Books/ACatalogueOfTheSamskritManuscriptsInTheAdyarLibraryPt.1/",
    "https://indianmanuscripts.com/",
    "https://niimh.nic.in/ebooks/ayuhandbook/index.php",
]

# Directories and metadata file
DOWNLOAD_DIR = os.path.join("output", "files")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

METADATA_FILE = os.path.join("output", "crawling_records.json")
if os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        records = json.load(f)
else:
    records = []

class Crawler:
    def __init__(self, base_url):
        self.base_url = base_url
        self.visited = set()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # robots.txt
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

        if not self.robots.can_fetch("*", url):
            logger.info(f"Disallowed by robots.txt: {url}")
            return

        try:
            logger.info(f"Fetching: {url}")
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return

        content_type = resp.headers.get("Content-Type", "").lower()

        # PDF / EPUB?
        is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")
        is_epub = "epub" in content_type or url.lower().endswith(".epub")
        if is_pdf or is_epub:
            self._download_file(url, resp, identified_url=None)
            return

        # HTML → parse links
        if "text/html" in content_type:
            soup = BeautifulSoup(resp.content, "html.parser")
            self._process_html_page(url, soup)
        else:
            logger.info(f"Skipping non-HTML: {url} ({content_type})")

    def _process_html_page(self, page_url, soup):
        time.sleep(2)  # polite delay
        for a in soup.select("a[href]"):
            href = a["href"].split('#')[0].strip()
            if not href:
                continue
            full = urljoin(page_url, href)

            if full.lower().endswith(('.pdf', '.epub')):
                if full not in self.visited:
                    try:
                        resp = self.session.get(full, timeout=REQUEST_TIMEOUT, stream=True)
                        resp.raise_for_status()
                        self._download_file(full, resp, identified_url=page_url)
                    except Exception as e:
                        logger.error(f"Failed downloading {full}: {e}")
            elif self._is_internal(full) and full not in self.visited:
                self.crawl(full)

    def _download_file(self, file_url, response, identified_url):
        try:
            # Construct local filename
            h = hashlib.sha256(file_url.encode()).hexdigest()[:8]
            name = os.path.basename(urlparse(file_url).path) or "document"
            ext = os.path.splitext(name)[1] or (
                ".pdf" if file_url.lower().endswith(".pdf") else ".epub"
            )
            if not name.endswith(ext):
                name += ext
            local_name = f"{h}_{name}"
            dest = os.path.join(DOWNLOAD_DIR, local_name)

            # Skip if already present with same size
            size_hdr = response.headers.get("Content-Length")
            if size_hdr and os.path.exists(dest) and os.path.getsize(dest) == int(size_hdr):
                logger.info(f"Already have {local_name}")
                return

            # Write to temp and move
            tmp = dest + ".tmp"
            with open(tmp, "wb") as f:
                total = 0
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
            if total == 0:
                raise ValueError("Empty download")
            os.replace(tmp, dest)
            logger.info(f"Saved {local_name} ({total} bytes)")

            # Record metadata
            record = {
                "identified_url": identified_url,
                "download_url": file_url,
                "file_name": local_name,
                "downloaded_at": datetime.utcnow().isoformat() + "Z"
            }
            records.append(record)
            with open(METADATA_FILE, "w", encoding="utf-8") as mf:
                json.dump(records, mf, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Error saving {file_url}: {e}")
            if os.path.exists(tmp):
                os.remove(tmp)

    def _is_internal(self, url):
        base_dom = urlparse(self.base_url).netloc
        dom = urlparse(url).netloc
        return dom == base_dom or dom.endswith("." + base_dom)

def test_url_accessibility(url):
    try:
        r = requests.head(url, headers={'User-Agent': USER_AGENT}, timeout=REQUEST_TIMEOUT)
        logger.info(f"{url} → {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Head failed {url}: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting Sanskrit Documents Crawler")
    for site in TARGET_SITES:
        if test_url_accessibility(site):
            logger.info(f"Crawling {site}")
            crawler = Crawler(site)
            crawler.crawl()
        else:
            logger.warning(f"Skipping inaccessible site: {site}")
    logger.info("Crawling completed")
