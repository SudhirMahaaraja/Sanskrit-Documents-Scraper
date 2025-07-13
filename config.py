# config.py - Configuration settings for the crawler

import os

# Request settings
REQUEST_TIMEOUT = (15, 60)  # (connect, read) timeouts
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds

# User agents to rotate through (helps avoid blocking)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
]

# Rate limiting
DELAY_BETWEEN_REQUESTS = 2  # seconds
DELAY_BETWEEN_DOWNLOADS = 3  # seconds

# Download settings
DOWNLOAD_DIR = os.path.join("output", "files")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MIN_FILE_SIZE = 1024  # 1KB

# Supported file types
SUPPORTED_EXTENSIONS = ['.pdf', '.epub', '.doc', '.docx']
SUPPORTED_CONTENT_TYPES = [
    'application/pdf',
    'application/epub+zip',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
]

# Sites with special handling requirements
SPECIAL_SITES = {
    'archive.org': {
        'requires_referrer': True,
        'delay': 5,
        'max_retries': 5
    },
    'indianculture.gov.in': {
        'requires_referrer': True,
        'delay': 3
    },
    'ignca.gov.in': {
        'delay': 4,
        'max_retries': 3
    }
}

# Proxy settings (if needed)
PROXIES = {
    # 'http': 'http://proxy.example.com:8080',
    # 'https': 'https://proxy.example.com:8080'
}

# Logging settings
LOG_LEVEL = 'INFO'
LOG_FILE = 'crawler.log'