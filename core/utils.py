import argparse
import logging
import pytesseract
from undetected_chromedriver import ChromeOptions

PAD_H_DEFAULT = 3.0
PAD_W_DEFAULT = 1.0

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Matchcut Generator: Create crops from web screenshots based on OCR.")
    parser.add_argument("-s", "--search-query", type=str, help="Query to search on DuckDuckGo.")
    parser.add_argument("-o", "--ocr-query", type=str, help="Text to look for in screenshots via OCR.")
    parser.add_argument("-k", "--keep-screenshots", action="store_true", help="Keep the full screenshot file after processing (default: False).")
    parser.add_argument("-m", "--max-results", type=int, default=5, help="Maximum number of search results to process.")
    parser.add_argument("-cv", "--chrome-version", type=int, default=144, help="Chrome version to use.")
    parser.add_argument("-sb", "--show-browser", action="store_true", help="Show the browser window (default: False, runs headless).")
    parser.add_argument("-mc", "--max-crops-per-link", type=int, default=10, help="Max crops per links.")
    parser.add_argument("-cp", "--chrome-path", type=str, help="Path to Chrome executable (optional).")
    parser.add_argument("-ph", "--pad-h", type=float, default=PAD_H_DEFAULT, help="Vertical padding multiplier (default: 5.0).")
    parser.add_argument("-pw", "--pad-w", type=float, default=PAD_W_DEFAULT, help="Horizontal padding multiplier (default: 1.0).")
    return parser.parse_args()

def check_tesseract() -> bool:
    """Checks if Tesseract is installed and configurable."""
    try:
        pytesseract.get_tesseract_version()
        logging.info("Tesseract found in PATH.")
        return True
    except (pytesseract.TesseractNotFoundError, SystemExit):
        pass
    return False

def check_chrome() -> bool:
    """Checks if Chrome is installed and accessible."""
    try:
        ChromeOptions().binary_location
        logging.info("Chrome found in PATH.")
        return True
    except Exception:
        return False
