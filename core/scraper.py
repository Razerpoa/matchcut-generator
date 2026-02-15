import sys
import time
import os
import logging
from ddgs import DDGS
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.common.exceptions import TimeoutException
import pytesseract

from .browser import get_limited_full_page_screenshot, handle_popups
from .vision import process_ocr_and_crop

def run_scraper(args, progress_callback=None):
    # Configure logging if no handlers exist
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

    driver = None

    try:
        logging.info("Starting scraper...")

        if progress_callback:
            progress_callback(0, 0, f"Searching for '{search_query}'...")
        
        logging.info(f"Searching DuckDuckGo for: {search_query}")
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=max_results))
        except Exception as e:
            logging.error(f"Search failed: {e}")
            if progress_callback:
                progress_callback(0, 0, "Error: Search failed. Check internet.")
            return

        if not results:
            logging.warning("No search results found.")
            if progress_callback:
                progress_callback(0, 0, "No results found.")
            return

        # Initialize Chrome Driver
        if progress_callback:
            progress_callback(0, 0, "Initializing Browser...")
        
        options = ChromeOptions()
        options.add_argument("--headless" if headless else "")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--mute-audio")

        try:
            driver = Chrome(options=options, version_main=args.chrome_version)
        except Exception as e:
            if "Binary Location Must be a String" in str(e) or isinstance(e, TypeError):
                 logging.error("Please install chrome or chromium first.")
            raise e
            
        driver.set_page_load_timeout(30)

        total_steps = len(results)
        
        for idx, result in enumerate(results):
            if progress_callback:
                progress_callback(idx, total_steps, f"Processing {idx+1}/{total_steps}: {result.get('title', 'Unknown')}")

            url = result.get('url') or result.get('href')
            if not url: continue

            logging.info(f"[{idx+1}/{len(results)}] Processing: {url}")

            try:
                try:
                    driver.get(url)
                except TimeoutException:
                    logging.warning(f"Wait timeout reached for {url}, proceeding...")

                time.sleep(2)
                handle_popups(driver)

                # Scroll to trigger lazy loading
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)

                screenshot_path = f"screenshot_{idx}.png"
                get_limited_full_page_screenshot(driver, screenshot_path)

                total_matches = 0
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
                     logging.error("Tesseract not found during processing.")
                     break
                except Exception as e:
                    logging.exception(f"OCR/Crop failed for site {idx}: {e}")

                if not args.keep_screenshots and os.path.exists(screenshot_path):
                    os.remove(screenshot_path)

            except Exception as e:
                logging.exception(f"Error processing {url}: {e}")
                continue
        
        if progress_callback:
             progress_callback(total_steps, total_steps, "Done!")

    except Exception as e:
        logging.exception(f"An error occurred: {e}")
    finally:
        if driver:
            logging.info("Cleaning up driver...")
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"Error closing driver: {e}")
