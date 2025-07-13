# Sanskrit Documents Scraper

A comprehensive Python-based web scraper designed to discover, download, and process Sanskrit documents from various academic and cultural heritage websites. This project focuses on building a robust pipeline for collecting and extracting text from Sanskrit manuscripts and documents available online.

## 🎯 Project Overview

The Sanskrit Documents Scraper is a multi-stage pipeline that:
1. **Crawls** multiple heritage websites to discover Sanskrit documents
2. **Downloads** PDF and EPUB files containing Sanskrit texts
3. **Extracts** metadata from downloaded documents
4. **Processes** text content using OCR for digitization
5. **Monitors** for updates using delta tracking

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Output Format](#output-format)
- [Detailed Technical Report](#detailed-technical-report)
- [Contributing](#contributing)
- [License](#license)

## ✨ Features

### Core Functionality
- **Multi-site Support**: Crawls Sanskrit documents from heritage websites including:
  - Sanskrit Documents Organization
  - Indian Culture Portal
  - Archive.org ASI Books
  - IGNCA Digital Library
  - Indian Manuscripts Portal
  - NIIMH E-books

- **Intelligent Crawling**: 
  - Respects robots.txt
  - Implements polite delays
  - Handles site-specific requirements
  - User-agent rotation

- **Robust Downloads**:
  - Resume capability
  - File integrity verification
  - Duplicate detection
  - Size validation

- **OCR Text Extraction**:
  - Multi-language support (Sanskrit, Hindi, English)
  - Uses Tesseract OCR engine
  - Handles complex Sanskrit scripts

- **Delta Tracking**:
  - Monitors documents for updates
  - Incremental downloading
  - Change detection via checksums and timestamps

## 🚀 Installation

### Prerequisites
- Python 3.8+
- Tesseract OCR engine
- Poppler utilities (for PDF processing)

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-san
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install tesseract
brew install poppler
```

**Windows:**
- Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
- Download and install Poppler from: https://blog.alivate.com.au/poppler-windows/

### Python Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
PyPDF2>=3.0.0
pdfminer.six>=20221105
pdf2image>=1.16.0
pytesseract>=0.3.10
```

## 📖 Usage

### Quick Start

Run the complete pipeline:
```bash
python main.py
```

### Individual Components

**1. Crawling Documents:**
```bash
python crawler.py
```

**2. Extracting Metadata:**
```bash
python metadata.py
```

**3. OCR Text Extraction:**
```bash
python extractor.py
```

**4. Delta Tracking:**
```bash
python delta.py
```

### Configuration

Edit `config.py` to customize:
- Download timeouts and retry settings
- Supported file types
- Site-specific handling
- Rate limiting parameters

## 📁 Project Structure

```
sanskrit-scraper/
├── main.py                 # Main orchestrator script
├── crawler.py              # Web crawling logic
├── metadata.py             # Document metadata extraction
├── extractor.py            # OCR text extraction
├── delta.py                # Change tracking and updates
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── output/                # Output directory
    ├── files/             # Downloaded documents
    ├── crawling_records.json      # Crawling metadata
    ├── metadata_records.jsonl    # Document metadata
    ├── extract_records.jsonl     # Extracted text
    └── delta_records.jsonl       # Change tracking
```

## 🔧 Configuration

### Key Settings in `config.py`:

```python
# Request timeouts
REQUEST_TIMEOUT = (15, 60)  # (connect, read)
RETRY_ATTEMPTS = 3

# Rate limiting
DELAY_BETWEEN_REQUESTS = 2  # seconds
DELAY_BETWEEN_DOWNLOADS = 3  # seconds

# File constraints
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MIN_FILE_SIZE = 1024  # 1KB

# Supported formats
SUPPORTED_EXTENSIONS = ['.pdf', '.epub', '.doc', '.docx']
```

## 📊 Output Format

### Metadata Records (JSONL)
```json
{
  "site": "sanskritdocuments.org",
  "document_id": "manuscript_001",
  "title": "Bhagavad Gita Commentary",
  "authors": ["Shankaracharya"],
  "pub_year": "1995-01-01",
  "language": "Sanskrit",
  "download_url": "https://...",
  "checksum": "sha256hash",
  "file_size": 2048576,
  "scraped_at": "2024-01-15T10:30:00Z"
}
```

### Text Extraction Records (JSONL)
```json
{
  "document_id": "manuscript_001",
  "content": "Extracted Sanskrit text content...",
  "content_length": 1500
}
```

---

## 📋 Detailed Technical Report

### Project Approach and Architecture

#### 1. **Modular Pipeline Design**

The project adopts a modular architecture with distinct phases:

**Phase 1: Web Crawling (`crawler.py`)**
- Implements a respectful web crawler following robots.txt
- Uses session management for connection persistence
- Handles site-specific requirements (referrer headers, delays)
- Discovers document links through recursive HTML parsing

**Phase 2: Metadata Extraction (`metadata.py`)**
- Extracts PDF metadata using multiple libraries (PyPDF2, pdfminer)
- Generates standardized metadata records
- Links crawling information with document properties

**Phase 3: Text Extraction (`extractor.py`)**
- Converts PDF pages to images using pdf2image
- Applies OCR using Tesseract with multi-language support
- Handles Sanskrit, Hindi, and English text recognition

**Phase 4: Delta Tracking (`delta.py`)**
- Monitors documents for changes using HTTP headers
- Maintains SQLite database for state tracking
- Implements intelligent re-download logic

#### 2. **Key Technical Decisions**

**Web Scraping Strategy:**
- **Choice**: Recursive crawling with HTML parsing
- **Rationale**: Sanskrit heritage sites often have deep link structures
- **Trade-off**: Slower than API-based approaches but more comprehensive

**OCR Implementation:**
- **Choice**: Tesseract with multi-language support
- **Rationale**: Open-source, supports Sanskrit scripts
- **Trade-off**: Accuracy varies with document quality; computationally intensive

**Storage Format:**
- **Choice**: JSONL for records, raw files for documents
- **Rationale**: Streaming-friendly, human-readable, standard format
- **Trade-off**: Larger storage footprint than binary formats

**Delta Tracking:**
- **Choice**: Hybrid approach using Last-Modified headers and checksums
- **Rationale**: Handles servers with/without proper HTTP headers
- **Trade-off**: Requires full file download for checksum verification

#### 3. **Architecture Trade-offs**

**Scalability vs. Simplicity:**
- **Chosen**: Single-threaded processing with session reuse
- **Benefits**: Simpler error handling, respects rate limits
- **Limitations**: Slower processing for large document collections
- **Future Enhancement**: Could implement async processing with semaphores

**Robustness vs. Performance:**
- **Chosen**: Multiple fallback mechanisms (PDF readers, metadata extraction)
- **Benefits**: Handles diverse document formats and quality
- **Limitations**: Additional dependencies and processing overhead

**Storage vs. Processing:**
- **Chosen**: Store original files + extracted text separately
- **Benefits**: Allows reprocessing with improved algorithms
- **Limitations**: Higher storage requirements

#### 4. **Error Handling Strategy**

**Graceful Degradation:**
- Individual document failures don't stop the entire pipeline
- Metadata extraction falls back to filename-based titles
- OCR failures are logged but don't prevent crawling

**Retry Logic:**
- Exponential backoff for network failures
- Site-specific retry counts based on observed behavior
- Permanent failure tracking to avoid infinite loops

#### 5. **Performance Considerations**

**Memory Management:**
- Streaming downloads for large files
- Page-by-page OCR processing to limit memory usage
- Connection pooling via requests.Session

**I/O Optimization:**
- Atomic file operations (temp files + rename)
- Batch metadata writes to JSONL files
- SQLite for efficient delta tracking queries

#### 6. **Cultural and Technical Challenges**

**Sanskrit Text Recognition:**
- **Challenge**: Complex scripts, multiple writing systems
- **Solution**: Multi-language Tesseract configuration
- **Limitation**: OCR accuracy varies significantly

**Heritage Site Compatibility:**
- **Challenge**: Sites with anti-scraping measures
- **Solution**: Site-specific configuration, respectful crawling
- **Ongoing**: Manual intervention needed for some sites

**Document Format Diversity:**
- **Challenge**: Mixed quality PDFs, scanned documents
- **Solution**: Multiple PDF parsing libraries, fallback mechanisms
- **Limitation**: Some documents may be unprocessable

#### 7. **Quality Assurance**

**Data Validation:**
- File size checks to detect error pages
- PDF format validation before processing
- Checksum verification for data integrity

**Monitoring:**
- Comprehensive logging throughout pipeline
- Success/failure statistics
- Processing time tracking

#### 8. **Future Enhancements**

**Immediate Improvements:**
- Implement parallel processing for OCR tasks
- Add support for additional document formats (DOCX, RTF)
- Implement machine learning for document classification

**Long-term Vision:**
- Named Entity Recognition for Sanskrit texts
- Automated translation capabilities
- Integration with digital humanities platforms

#### 9. **Resource Requirements**

**Computational:**
- OCR processing: CPU-intensive, ~30-60 seconds per page
- PDF conversion: Memory-intensive, ~50-100MB per document
- Storage: ~1-5GB per 1000 documents (original + extracted)

**Network:**
- Respectful crawling: 2-3 seconds between requests
- Estimated throughput: 100-500 documents per hour
- Bandwidth: Depends on document sizes, typically 10-50MB/hour

### Conclusion

This Sanskrit Documents Scraper represents a comprehensive solution for heritage document digitization. The modular architecture allows for easy maintenance and extension, while the robust error handling ensures reliable operation across diverse web environments. The trade-offs made prioritize data quality and system reliability over raw processing speed, making it suitable for academic and cultural preservation applications.

The project successfully addresses the unique challenges of Sanskrit document processing while maintaining compatibility with modern web scraping practices and ethical crawling standards.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Sanskrit Documents Organization for providing accessible digital texts
- Indian cultural heritage institutions for preserving these valuable documents
- Open-source OCR community for making text extraction possible
- Contributors to the various Python libraries that make this project possible

---

*This project is developed for educational and cultural preservation purposes. Please respect the terms of use of source websites and copyright holders.*