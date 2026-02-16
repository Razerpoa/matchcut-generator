import time
import os
import logging
from ddgs import DDGS
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.common.exceptions import TimeoutException
import pytesseract

from .browser import get_limited_full_page_screenshot, handle_popups, get_site_mode
from .vision import process_ocr_and_crop
from .utils import PAD_H_DEFAULT, PAD_W_DEFAULT

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
    site_mode_pref = getattr(args, 'site_mode', 'any')

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
        
        results = []
        try:
            with DDGS() as ddgs:
                # Initially fetch more than max_results to reduce refills
                search_limit = max_results * 2 if site_mode_pref != "any" else max_results
                results = list(ddgs.text(search_query, max_results=search_limit))
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
        if headless:
            options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--mute-audio")

        try:
            driver = Chrome(options=options, version_main=args.chrome_version)
        except Exception as e:
            if "Binary Location Must be a String" in str(e) or isinstance(e, TypeError):
                 logging.error("Please install chrome or chromium first.")
            raise e
            
        driver.set_page_load_timeout(30)

        valid_sites_processed = 0
        idx = 0
        removed_sites_count = 0
        
        while valid_sites_processed < max_results and idx < len(results):
            result = results[idx]
            idx += 1
            
            if progress_callback:
                progress_callback(valid_sites_processed, max_results, f"Processing {valid_sites_processed+1}/{max_results}: {result.get('title', 'Unknown')}")

            url = result.get('url') or result.get('href')
            if not url: continue

            logging.info(f"Processing ({valid_sites_processed+1}/{max_results}): {url}")

            try:
                try:
                    driver.get(url)
                except TimeoutException:
                    logging.warning(f"Wait timeout reached for {url}, proceeding...")

                time.sleep(2)
                handle_popups(driver)

                # Check Mode Preference
                should_invert = False
                should_bw = False
                if site_mode_pref != "any":
                    actual_mode = get_site_mode(driver)
                    if actual_mode != site_mode_pref:
                        pref_invert = getattr(args, 'invert_mismatched', False)
                        pref_bw = getattr(args, 'bw_mismatched', False)

                        if pref_invert or pref_bw:
                            logging.info(f"Site {url} is {actual_mode} mode, but user preferred {site_mode_pref} mode. Applying requested filters (Invert={pref_invert}, B&W={pref_bw}).")
                            should_invert = pref_invert
                            should_bw = pref_bw
                        else:
                            logging.warning(f"Site {url} is {actual_mode} mode, but user preferred {site_mode_pref} mode. Removing site.")
                            removed_sites_count += 1
                            
                            # Try to fetch another result if we are running low
                            if (len(results) - idx) < (max_results - valid_sites_processed):
                                logging.info(f"Fetching additional search results (Removed: {removed_sites_count})")
                                try:
                                    with DDGS() as ddgs:
                                        # Skip results we already have
                                        more_results = list(ddgs.text(search_query, max_results=len(results) + 5))
                                        for mr in more_results:
                                            if mr not in results:
                                                results.append(mr)
                                except Exception as e:
                                    logging.error(f"Failed to fetch additional results: {e}")
                            
                            continue

                # Scroll to trigger lazy loading
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)

                screenshot_path = f"screenshot_{valid_sites_processed}.png"
                get_limited_full_page_screenshot(driver, screenshot_path)

                try:
                    matches = process_ocr_and_crop(
                        screenshot_path,
                        ocr_query,
                        prefix=f"site_{valid_sites_processed}_{ocr_query.replace(' ', '_')}",
                        max_crops=max_crops_per_link,
                        pad_h=getattr(args, 'pad_h', PAD_H_DEFAULT),
                        pad_w=getattr(args, 'pad_w', PAD_W_DEFAULT),
                        invert_color=should_invert,
                        bw_color=should_bw
                    )
                    logging.info(f"Finished processing site {valid_sites_processed}. Matches: {matches}")
                    valid_sites_processed += 1
                except pytesseract.TesseractNotFoundError:
                     logging.error("Tesseract not found during processing.")
                     break
                except Exception as e:
                    logging.exception(f"OCR/Crop failed for site {valid_sites_processed}: {e}")

                if not args.keep_screenshots and os.path.exists(screenshot_path):
                    os.remove(screenshot_path)

            except Exception as e:
                logging.exception(f"Error processing {url}: {e}")
                continue
        
        logging.info(f"Scraping finished. Total valid sites: {valid_sites_processed}, Removed sites: {removed_sites_count}")
        
        if progress_callback:
             progress_callback(max_results, max_results, f"Done! (Processed {valid_sites_processed}, Removed {removed_sites_count})")

    except Exception as e:
        logging.exception(f"An error occurred: {e}")
    finally:
        if driver:
            logging.info("Cleaning up driver...")
            try:
                driver.quit()
            except Exception as e:
                logging.error(f"Error closing driver: {e}")
