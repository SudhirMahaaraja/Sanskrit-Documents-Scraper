import os
import json
import hashlib
from datetime import datetime
from PyPDF2 import PdfReader
from urllib.parse import urlparse

OUTPUT_JSONL = os.path.join("output", "records.jsonl")
os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)

def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def extract_pdf_metadata(path):
    reader = PdfReader(path)
    info = reader.metadata or {}
    title = info.title or ""
    author = info.author or ""
    # PDF doesn't always embed dates cleanly; fallback to file timestamp
    raw_date = info.creation_date or None
    try:
        pub_year = datetime.strptime(raw_date[2:], "%Y%m%d%H%M%S").date().isoformat() if raw_date else None
    except:
        pub_year = datetime.utcfromtimestamp(os.path.getmtime(path)).date().isoformat()
    return title, author, pub_year

def build_record(file_path, source_url):
    domain = urlparse(source_url).netloc
    checksum = sha256_of_file(file_path)
    title, author, pub_year = extract_pdf_metadata(file_path)
    record = {
        "site": domain,
        "document_id": os.path.splitext(os.path.basename(file_path))[0],
        "title": title,
        "authors": [author] if author else [],
        "pub_year": pub_year,
        "language": "Unknown",
        "download_url": source_url,
        "checksum": checksum,
        "scraped_at": datetime.utcnow().isoformat() + "Z"
    }
    return record

def append_record(record):
    with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

if __name__ == "__main__":
    # Example: process all files in output/files
    files_dir = os.path.join("output", "files")
    for fname in os.listdir(files_dir):
        path = os.path.join(files_dir, fname)
        rec = build_record(path, source_url="file://" + path)
        append_record(rec)
        print("Recorded:", rec["document_id"])
