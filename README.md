# Sanskrit Documents Scraper

A Python-based microservice for crawling, downloading, and processing Sanskrit manuscripts and e-books from various cultural heritage websites. The tool automates:

* Recursive crawling of target domains
* Downloading PDFs, EPUBs, and HTML documents
* Metadata extraction (title, author, publication date, language, unique ID)
* SHA-256 checksum computation for change detection
* Text extraction from embedded content or via Tesseract OCR
* Delta processing to re-download only updated documents
* JSON output with ISO-8601 timestamps and schema validation

---

## 🚀 Features

1. **Crawl & Download**

   * Respects `robots.txt` rules
   * Configurable delay (1–2 seconds) between requests
   * Recursively fetches internal links and downloads documents

2. **Metadata Extraction**

   * Extracts title, author/editor, publication year, language
   * Constructs a unique `document_id`
   * Computes SHA-256 checksum for each file

3. **Text Extraction & OCR**

   * Direct text extraction for searchable PDFs (via PDFMiner/Tika)
   * Tesseract OCR fallback for scanned-only documents

4. **Delta Processing**

   * Uses HTTP `Last-Modified` headers and checksum comparison
   * Only re-downloads and re-processes changed or new files

5. **Structured JSON Output**

   * Line-delimited JSON (`.jsonl`) per document
   * Follows a consistent schema (see `schema.json`)
   * ISO 8601 date formats and normalized author names

## 📁 Project Structure

```bash
sanskrit_scraper/
├── crawler.py            # Crawl & download logic
├── metadata.py           # Metadata extraction functions
├── extractor.py          # Text extraction & OCR routines
├── delta.py              # Delta processing implementation
├── schema.json           # JSON Schema for validation
├── requirements.txt      # Python dependencies
└── output/               # Downloaded files & JSON records
    ├── files/            # Raw PDF/EPUB/HTML files
    └── records.jsonl     # Line-delimited JSON output
```

## ⚙️ Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/sanskrit_scraper.git
   cd sanskrit_scraper
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## 🎯 Usage

1. **Configure target sites** in `crawler.py` (update the `sites` list).

2. **Run the crawler** to download documents:

   ```bash
   python crawler.py
   ```

3. **Extract metadata** and append JSON records:

   ```bash
   python metadata.py
   ```

4. **Generate text content** (OCR if needed):

   ```bash
   python extractor.py
   ```

5. **Enable delta processing** for incremental updates:

   ```bash
   python delta.py
   ```

## ✅ Testing

The repository includes test cases for each module. To validate:

```bash
pytest tests/
```

Ensure all tests pass (TC1 … TC5) before submitting.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Please check `CONTRIBUTING.md` for guidelines.

## 📄 License

This project is licensed under the MIT License. See `LICENSE` for details.
