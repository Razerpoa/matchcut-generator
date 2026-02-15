import pytesseract
import sys
import time
import os
import base64
from ddgs import DDGS
from PIL import Image
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
import cv2
import numpy as np
import argparse
import logging

def get_limited_full_page_screenshot(driver: Chrome, path: str, limit: int = 4096) -> None:
    """Captures the page up to a specific height limit and stops."""
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    width = metrics['contentSize']['width']
    actual_height = metrics['contentSize']['height']

    # Clamping logic: Use the actual height unless it exceeds the limit
    capture_height = min(actual_height, limit)

    if actual_height > limit:
        logging.warning(f"Page is {actual_height}px. Limiting capture to {limit}px.")

    # Apply the dimensions
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": width,
        "height": capture_height,
        "deviceScaleFactor": 1,
        "mobile": False
    })

    # Capture the image
    screenshot_data = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "format": "jpeg",      # CHANGED from png
        "quality": 80,         # ADDED: Much faster encoding
        "clip": {
            "x": 0,
            "y": 0,
            "width": width,
            "height": capture_height,
            "scale": 1
        },
        "fromSurface": True,
        "captureBeyondViewport": False
    })

    with open(path, "wb") as f:
        f.write(base64.b64decode(screenshot_data['data']))

    # Clean up
    driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
    logging.info(f"Screenshot saved: {path}")

def handle_popups(driver: Chrome) -> None:
    dismiss_keywords = ["Lain kali", "Not now", "No thanks", "Close", "Tutup"]

    # XPaths for text matches and common 'x' button attributes/symbols
    selectors = [
        *[f"//*[contains(text(), '{text}')]" for text in dismiss_keywords],
        "//*[contains(@aria-label, 'Close') or contains(@aria-label, 'Tutup')]",
        "//*[contains(@class, 'close') or contains(@class, 'Close')]",
        "//button[text()='x' or text()='X' or text()='×']"
    ]

    for xpath in selectors:
        try:
            element = driver.find_element(By.XPATH, xpath)
            if element.is_displayed():
                ActionChains(driver).move_to_element(element).click().perform()
                logging.info(f"Dismissed popup using: {xpath}")
                time.sleep(1)
                return
        except:
            continue

    try:
        driver.execute_script("""
            var elements = document.querySelectorAll('button, div[role="button"], span, i');
            for (var i = 0; i < elements.length; i++) {
                var text = elements[i].innerText.trim().toLowerCase();
                var aria = (elements[i].getAttribute('aria-label') || "").toLowerCase();
                if (text === 'x' || text === '×' || text === 'close' || aria.includes('close') || text.includes('lain kali')) {
                    elements[i].click();
                    break;
                }
            }
        """)
    except Exception as e:
        logging.error(f"JS click failed: {e}")

    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except:
        pass

def preprocess_for_ocr(img: Image.Image) -> tuple[Image.Image, int]:
    # 1. Convert to Grayscale
    img = img.convert('L')

    # 2. Upscale the image (2x) - Very important for small web text
    width, height = img.size
    img = img.resize((width * 2, height * 2), resample=Image.Resampling.LANCZOS)

    # 3. Convert to OpenCV format for thresholding
    open_cv_image = np.array(img)

    # 4. Apply Otsu's Thresholding (converts to pure B&W)
    _, thresh = cv2.threshold(open_cv_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(thresh), 2 # Return image and the scale factor

def process_ocr_and_crop(image_path: str, search_text: str, output_dir: str = "crops", prefix: str = "match", max_crops: int = 10) -> int:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    original_img = Image.open(image_path)
    processed_img, scale_factor = preprocess_for_ocr(original_img)
    img_width, img_height = processed_img.size

    # config: psm 3 is often better for layouts; psm 11 for sparse text
    # We use image_to_boxes to get character level data
    # Format: char left bottom right top page
    config = '--psm 3' 
    boxes_string = pytesseract.image_to_boxes(processed_img, config=config)

    found_count = 0
    search_text_normalized = search_text.lower().replace(" ", "")
    
    if not boxes_string:
        logging.info(f"No text found in image for '{search_text}'.")
        return 0

    # Parse boxes
    chars = []
    boxes = []
    
    for line in boxes_string.splitlines():
        parts = line.split()
        if len(parts) >= 6:
            char = parts[0]
            # Tesseract coordinates are bottom-left origin
            # left, bottom, right, top
            left = int(parts[1])
            bottom = int(parts[2])
            right = int(parts[3])
            top = int(parts[4])
            
            # Convert to PIL/CV2 top-left origin
            # y_pil = height - y_tess
            # top_pil = height - top_tess
            # bottom_pil = height - bottom_tess
            
            # Tesseract 'top' is actually the y-coordinate of the top of the letter in its coordinate system (further from 0)
            # Tesseract 'bottom' is the y-coordinate of the bottom (closer to 0)
            
            # In PIL (0,0 is top-left):
            # new_top = img_height - top
            # new_bottom = img_height - bottom
            
            y1 = img_height - top
            y2 = img_height - bottom
            
            chars.append(char.lower())
            boxes.append((left, y1, right, y2))

    full_text_continuous = "".join(chars)
    
    # Simple search for the sequence
    start_index = 0
    while found_count < max_crops:
        try:
            match_index = full_text_continuous.index(search_text_normalized, start_index)
        except ValueError:
            break
            
        # We found a match starting at match_index
        # The match covers len(search_text_normalized) characters
        end_index = match_index + len(search_text_normalized)
        
        # Get bounding box of this sequence
        match_boxes = boxes[match_index:end_index]
        if not match_boxes: 
            start_index = match_index + 1
            continue
            
        # Calculate union box
        min_x = min(b[0] for b in match_boxes)
        min_y = min(b[1] for b in match_boxes)
        max_x = max(b[2] for b in match_boxes)
        max_y = max(b[3] for b in match_boxes)
        
        # Scale back to original image
        x = min_x // scale_factor
        y = min_y // scale_factor
        w = (max_x - min_x) // scale_factor
        h = (max_y - min_y) // scale_factor
        
        # Padding
        pad_h = h * 3 # vertical padding
        pad_w = w * 1 # add some horizontal padding too
        
        left = max(0, x - pad_w)
        top = max(0, y - pad_h)
        right = min(original_img.width, x + w + pad_w)
        bottom = min(original_img.height, y + h + pad_h)
        
        crop_img = original_img.crop((left, top, right, bottom))
        crop_filename = f"{prefix.replace(' ', '_')}_{found_count}.png"
        crop_path = os.path.join(output_dir, crop_filename)
        crop_img.save(crop_path)
        
        logging.info(f"Match found: '{search_text}' at ({x}, {y})")
        found_count += 1
        
        # Move start index forward to find next occurrence
        # We move by 1 to find overlapping matches? usually we want distinct matches
        # let's move by length of match to avoid partial overlaps of same word if that's preferred, 
        # or just +1 to find all possibilities. Let's do + len for distinct
        start_index = match_index + len(search_text_normalized)

    if found_count == 0:
        logging.info(f"No reliable matches for '{search_text}'.")
    return found_count

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
    return parser.parse_args()

def find_chrome_executable() -> str:
    """Finds the Chrome/Chromium executable across Windows and Linux."""
    if sys.platform == "win32":
        paths = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LocalAppData", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
    else: # Linux/Mac
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            "/opt/google/chrome/google-chrome",
        ]

    for path in paths:
        if os.path.exists(path):
            return path
    
    # If not found in common paths, try 'which' on Linux or just return None
    if sys.platform != "win32":
        import shutil
        return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
        
    return None

def run_scraper(args, progress_callback=None):
    # Configure logging
    # Note: BasicConfig should only be called if handlers aren't set, 
    # but here we might want to just let the main/gui handle logging config.
    # We can keep it or remove it if we rely on the caller to setup logging.
    # For now, I'll keep it but it might be redundant if main sets it up.
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
    
    search_query = args.search_query
    ocr_query = args.ocr_query
    max_results = args.max_results
    max_crops_per_link = args.max_crops_per_link
    headless = not args.show_browser

    if not search_query:
        logging.error("Search Query is required. Aborting.")
        if progress_callback:
            progress_callback(0, 0, "Error: Search Query missing.")
        return

    if not ocr_query or len(ocr_query) < 4:
        logging.warning(f"OCR Query '{ocr_query}' is too short (min 4 chars) or missing. Aborting.")
        if progress_callback:
            progress_callback(0, 0, "Error: OCR Query too short/missing.")
        return

    driver = None # Initialize driver to None

    try:
        logging.info("Starting scraper...")

        if progress_callback:
            progress_callback(0, 0, f"Searching for '{search_query}'...")
        print(f"DEBUG: Starting DDGS search for '{search_query}'...", file=sys.stderr)
        logging.info(f"Searching DuckDuckGo for: {search_query}")
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=max_results))
            print(f"DEBUG: DDGS search returned {len(results)} results.", file=sys.stderr)
        except Exception as e:
            logging.error(f"Search failed: {e}")
            if progress_callback:
                progress_callback(0, 0, "Error: Search failed. Check internet.")
            return

        if not results:
            logging.warning("No search results found. Please check your internet connection or query.")
            if progress_callback:
                progress_callback(0, 0, "No results found.")
            return

        # Initialize Chrome Driver
        if progress_callback:
            progress_callback(0, 0, "Initializing Browser...")
        print("DEBUG: Initializing Chrome driver...", file=sys.stderr)
        
        options = ChromeOptions()
        options.add_argument("--headless" if headless else "")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--mute-audio") # Mute audio

        chrome_path = getattr(args, 'chrome_path', None) or find_chrome_executable()
        
        if chrome_path:
             logging.info(f"Using Chrome binary at: {chrome_path}")
             options.binary_location = chrome_path
        else:
             logging.warning("Chrome binary path not found automatically. undetected_chromedriver will try to locate it.")

        try:
            driver = Chrome(options=options, version_main=args.chrome_version)
        except Exception as e:
            if "Binary Location Must be a String" in str(e) or isinstance(e, TypeError):
                 logging.error("Failed to initialize Chrome: Binary Location Must be a String or not found. "
                               "Please specify --chrome-path manually.")
            raise e
            
        driver.set_page_load_timeout(30) # Increased timeout
        print("DEBUG: Chrome driver initialized.", file=sys.stderr)

        total_steps = len(results)
        
        for idx, result in enumerate(results):
            if progress_callback:
                progress_callback(idx, total_steps, f"Processing {idx+1}/{total_steps}: {result.get('title', 'Unknown')}")

            # DDGS news results use 'url' key, text results use 'href'
            url = result.get('url') or result.get('href')
            if not url: continue

            logging.info(f"[{idx+1}/{len(results)}] Processing: {url}")

            try:
                try:
                    driver.get(url)
                except TimeoutException:
                    logging.warning(f"Wait timeout reached for {url}, proceeding with available content...")

                time.sleep(2) # Give a bit more time for stable state

                handle_popups(driver)

                # Scroll to trigger lazy loading
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)

                screenshot_path = f"screenshot_{idx}.png"
                get_limited_full_page_screenshot(driver, screenshot_path)

                # Use the query keywords for OCR matching
                # We'll try to find any part of the query in the page
                # search_keywords = query.split()
                total_matches = 0
                if len(ocr_query) < 4: 
                    logging.warning(f"OCR Query '{ocr_query}' is too short (min 4 chars). Skipping OCR.")
                    continue # Skip short words
                
                try:
                    matches = process_ocr_and_crop(
                        screenshot_path,
                        ocr_query,
                        prefix=f"site_{idx}_{ocr_query.replace(' ', '_')}",
                        max_crops=max_crops_per_link
                    )
                    total_matches += matches
                    logging.info(f"Finished processing site {idx}. Total matches found: {total_matches}")
                except pytesseract.TesseractNotFoundError:
                     logging.error("Tesseract not found during processing. Please install Tesseract.")
                     break # Stop processing if Tesseract is missing
                except Exception as e:
                    logging.exception(f"OCR/Crop failed for site {idx}: {e}")

                if not args.keep_screenshots and os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                    logging.info(f"Removed screenshot: {screenshot_path}")

            except Exception as e:
                logging.exception(f"Error processing {url}: {e}")
                continue
        
        if progress_callback:
             progress_callback(total_steps, total_steps, "Done!")

    except Exception as e:
        logging.exception(f"An error occurred during search or initialization: {e}")
    finally:
        if driver:
            logging.info("Cleaning up driver...")
            try:
                driver.quit()
            except OSError:
                pass # Ignore 'handle is invalid' errors common in Windows
            except Exception as e:
                logging.error(f"Error closing driver: {e}")

def check_tesseract() -> bool:
    """Checks if Tesseract is installed and configurable."""
    # 1. Check if it's already in PATH
    try:
        pytesseract.get_tesseract_version()
        logging.info("Tesseract found in PATH.")
        return True
    except (pytesseract.TesseractNotFoundError, SystemExit):
        pass
            
    return False
