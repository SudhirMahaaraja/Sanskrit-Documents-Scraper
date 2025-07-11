import os
import time
import hashlib
import requests
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup

# 10 s connect timeout, 30 s read timeout
REQUEST_TIMEOUT = (10, 30)
USER_AGENT = "Mozilla/5.0 (compatible; SanskritDocsBot/1.0)"

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
        rp = RobotFileParser()
        rp.set_url(urljoin(base_url, "/robots.txt"))
        try:
            rp.read()
        except:
            pass
        self.robots = rp

    def crawl(self, url=None):
        url = url or self.base_url
        if url in self.visited:
            return
        self.visited.add(url)

        if self.robots.can_fetch("*", url) is False:
            return

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )
        except requests.RequestException as e:
            print(f"[ERROR] {e} fetching {url}")
            return

        content_type = resp.headers.get("Content-Type", "")
        # If it's a PDF or EPUB (by header or URL suffix), download it
        if any(x in content_type for x in ("pdf", "epub")) or url.lower().endswith((".pdf", ".epub")):
            self._download_file(url, resp)
            return

        # Otherwise, parse HTML and recurse
        try:
            html = resp.content
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"[ERROR] parsing HTML at {url}: {e}")
            return

        time.sleep(1.5)  # rate limit
        for link in soup.select("a[href]"):
            href = link["href"].split('#')[0]  # drop fragments
            full = urljoin(url, href)
            if self._is_internal(full):
                self.crawl(full)

    def _download_file(self, file_url, response):
        # Generate a stable filename based on URL
        fname_hash = hashlib.sha256(file_url.encode('utf-8')).hexdigest()[:8]
        path = urlparse(file_url).path
        basename = os.path.basename(path)
        if not basename:
            basename = "download"
        local_name = f"{fname_hash}_{basename}"
        local_path = os.path.join(DOWNLOAD_DIR, local_name)

        # Skip if already fully downloaded
        if os.path.exists(local_path) and os.path.getsize(local_path) == int(response.headers.get("Content-Length", -1)):
            return

        try:
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            print(f"[ERROR] saving {file_url}: {e}")
            if os.path.exists(local_path):
                os.remove(local_path)
            return

        print(f"Downloaded {file_url} → {local_path}")

    def _is_internal(self, url):
        return urlparse(url).netloc.endswith(urlparse(self.base_url).netloc)

if __name__ == "__main__":
    for site in TARGET_SITES:
        print(f"Starting crawl: {site}")
        Crawler(site).crawl()
