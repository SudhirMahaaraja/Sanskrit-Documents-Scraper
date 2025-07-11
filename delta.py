import os
import sqlite3
import requests
import hashlib
from datetime import datetime

DB_PATH = "delta.db"
DOWNLOAD_DIR = os.path.join("output", "files")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            url TEXT PRIMARY KEY,
            last_modified TEXT,
            checksum TEXT
        )
    """)
    conn.commit()
    return conn

def process_url(url):
    conn = init_db()
    c = conn.cursor()
    head = requests.head(url, allow_redirects=True)
    lm = head.headers.get("Last-Modified")
    c.execute("SELECT last_modified, checksum FROM docs WHERE url=?", (url,))
    row = c.fetchone()

    needs = False
    if row:
        stored_lm, stored_cs = row
        if lm and lm != stored_lm:
            needs = True
    else:
        needs = True

    if needs:
        resp = requests.get(url)
        fname = os.path.basename(url)
        local_path = os.path.join(DOWNLOAD_DIR, fname)
        with open(local_path, "wb") as f:
            f.write(resp.content)
        new_cs = sha256(local_path)
        # update
        c.execute("""
            INSERT INTO docs(url, last_modified, checksum)
            VALUES(?,?,?)
            ON CONFLICT(url) DO UPDATE
              SET last_modified=excluded.last_modified,
                  checksum=excluded.checksum
        """, (url, lm, new_cs))
        conn.commit()
        print(f"Processed & updated: {url}")
    else:
        print(f"No change: {url}")
    conn.close()

if __name__ == "__main__":
    # Example usage: re‐process all known URLs from a file or list
    urls = []
    for f in os.listdir(DOWNLOAD_DIR):
        if "_" in f:
            urls.append(f)
    # In practice, keep a list of source URLs instead of filenames
    for u in urls:
        process_url(u)
