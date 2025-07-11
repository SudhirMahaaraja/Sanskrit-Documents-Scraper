import os
from pdfminer.high_level import extract_text
from PIL import Image
import pytesseract

OUTPUT_JSONL = os.path.join("output", "records.jsonl")

def extract_text_from_pdf(path):
    # try embedded text
    try:
        txt = extract_text(path)
        if txt.strip():
            return txt
    except:
        pass
    # fallback to OCR: convert each page to image via PIL (or use pdf2image)
    from pdf2image import convert_from_path
    pages = convert_from_path(path)
    full_text = ""
    for page in pages:
        full_text += pytesseract.image_to_string(page) + "\n"
    return full_text

def attach_content():
    import json
    records = []
    with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            records.append(rec)
    for rec in records:
        file_id = rec["document_id"]
        # find corresponding file
        files = os.listdir(os.path.join("output", "files"))
        match = [f for f in files if f.startswith(file_id)]
        if not match:
            continue
        path = os.path.join("output", "files", match[0])
        txt = extract_text_from_pdf(path)
        rec["content"] = txt
    # overwrite JSONL
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

if __name__ == "__main__":
    attach_content()
    print("Content attached to all records.")
