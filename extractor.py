from pdf2image import convert_from_path
import pytesseract
import json
import os


pdf_input_dir = "output/files"


output_dir = "output"
output_jsonl_filename = os.path.join(output_dir, "extract_records.jsonl")


languages = 'eng+hin+san'


os.makedirs(output_dir, exist_ok=True)
print(f"Ensured output directory '{output_dir}' exists.")





processed_count = 0
failed_pdfs = []
print(f"\nScanning for PDF files in '{pdf_input_dir}'...")
try:
    all_files = os.listdir(pdf_input_dir)
except FileNotFoundError:
    print(f"Error: The directory '{pdf_input_dir}' does not exist. Please create it and place your PDFs inside.")
    exit()

pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]

if not pdf_files:
    print(f"No PDF files found in '{pdf_input_dir}'. Please place your PDF documents there.")
else:
    print(f"Found {len(pdf_files)} PDF files to process.")

for pdf_file_name in pdf_files:
    current_pdf_path = os.path.join(pdf_input_dir, pdf_file_name)
    document_id = os.path.splitext(pdf_file_name)[0]

    print(f"\n--- Processing PDF: '{pdf_file_name}' (ID: {document_id}) ---")

    try:

        print(f"Converting '{pdf_file_name}' to images...")
        pages = convert_from_path(current_pdf_path)
        print(f"Successfully converted {len(pages)} pages to images from '{pdf_file_name}'.")


        full_text = ""
        for i, page in enumerate(pages):
            print(f"  - Extracting text from Page {i+1}...")
            text = pytesseract.image_to_string(page, lang=languages)
            full_text += text + "\n"



        content_words = full_text.split()
        content_length = len(content_words)


        record_data = {
            "document_id": document_id,
            "content": full_text.strip(),
            "content_length": content_length
        }


        with open(output_jsonl_filename, "a", encoding="utf-8") as f:
            json.dump(record_data, f, ensure_ascii=False)
            f.write("\n")

        print(f"Successfully processed '{pdf_file_name}' and saved data to '{output_jsonl_filename}'.")
        print(f"  Content Length (words): {record_data['content_length']}")
        processed_count += 1

    except Exception as e:
        print(f"Error processing '{pdf_file_name}': {e}")
        failed_pdfs.append(pdf_file_name)

# --- Summary ---
print("\n--- Processing Summary ---")
print(f"Total PDFs found: {len(pdf_files)}")
print(f"PDFs successfully processed: {processed_count}")
if failed_pdfs:
    print(f"PDFs that failed to process: {len(failed_pdfs)}")
    for pdf_name in failed_pdfs:
        print(f"  - {pdf_name}")
print(f"All extracted data is saved in '{output_jsonl_filename}'")