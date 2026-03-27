# FloatNote

## Setup

1. Install Python dependencies:
   pip install -r requirements.txt

2. Install Tesseract OCR (required for screen reading):
   winget install UB-Mannheim.TesseractOCR
   
   Then add to PATH or set in ocr_processor.py:
   pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

3. Run the backend:
   python backend/main.py