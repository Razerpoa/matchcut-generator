import time
import os
import base64
from ddgs import DDGS
import pytesseract
from PIL import Image
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from PIL import ImageOps
import cv2
import numpy as np

def get_limited_full_page_screenshot(driver, path, limit=4096):
    """Captures the page up to a specific height limit and stops."""
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    width = metrics['contentSize']['width']
    actual_height = metrics['contentSize']['height']

    # Clamping logic: Use the actual height unless it exceeds the limit
    capture_height = min(actual_height, limit)

    if actual_height > limit:
        print(f"Note: Page is {actual_height}px. Limiting capture to {limit}px.")

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
        "captureBeyondViewport": True
    })

    with open(path, "wb") as f:
        f.write(base64.b64decode(screenshot_data['data']))

    # Clean up
    driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
    print(f"Screenshot saved: {path}")

def handle_popups(driver):
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
                print(f"Dismissed popup using: {xpath}")
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
        print(f"JS click failed: {e}")

    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except:
        pass

def preprocess_for_ocr(img):
    # 1. Convert to Grayscale
    img = img.convert('L')

    # 2. Upscale the image (2x) - Very important for small web text
    width, height = img.size
    img = img.resize((width * 2, height * 2), resample=Image.LANCZOS)

    # 3. Convert to OpenCV format for thresholding
    open_cv_image = np.array(img)

    # 4. Apply Otsu's Thresholding (converts to pure B&W)
    _, thresh = cv2.threshold(open_cv_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return Image.fromarray(thresh), 2 # Return image and the scale factor

def process_ocr_and_crop(image_path, search_text, output_dir="crops", prefix="match", max_crops=10):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    original_img = Image.open(image_path)
    processed_img, scale_factor = preprocess_for_ocr(original_img)

    # config: psm 3 is often better for layouts; psm 11 for sparse text
    config = '--psm 3'
    data = pytesseract.image_to_data(processed_img, output_type=pytesseract.Output.DICT, config=config)

    found_count = 0
    full_text = " ".join(data['text']).lower()
    search_text = search_text.lower()

    # Find the start index of our search query in the full text string
    if search_text in full_text:
        # We need to find which indices in the 'data' dict correspond to our search text
        words = search_text.split()

        for i in range(len(data['text']) - len(words) + 1):
            if found_count >= max_crops: break

            # Check if sequence of words matches
            match_segment = " ".join(data['text'][i:i+len(words)]).lower()

            if search_text in match_segment and int(data['conf'][i]) > 40:
                # Calculate bounding box for the whole phrase
                # Note: we must divide by scale_factor to map back to original image size
                x = min(data['left'][i:i+len(words)]) // scale_factor
                y = min(data['top'][i:i+len(words)]) // scale_factor
                w = sum(data['width'][i:i+len(words)]) // scale_factor
                h = max(data['height'][i:i+len(words)]) // scale_factor

                pad = h * 3
                left = max(0, x - pad)
                top = max(0, y - pad)
                right = min(original_img.width, x + w + pad)
                bottom = min(original_img.height, y + h + pad)

                crop_img = original_img.crop((left, top, right, bottom))
                crop_filename = f"{prefix.replace(' ', '_')}_{found_count}.png"
                crop_path = os.path.join(output_dir, crop_filename)
                crop_img.save(crop_path)

                print(f"Match found: '{match_segment}' at ({x}, {y})")
                found_count += 1

    if found_count == 0:
        print(f"No reliable matches for '{search_text}'.")
    return found_count

def main():
    query = "Cristiano Ronaldo"
    max_results = 5
    max_crops_per_link = 10
    do_news = False

    options = ChromeOptions()
    # options.add_argument("--headless") # Commented out for visibility, can be enabled
    options.add_argument("--window-size=1920,1080")

    driver = Chrome(options=options, version_main=144)
    driver.set_page_load_timeout(5)

    try:
        print(f"Searching DuckDuckGo for news: {query}")
        with DDGS() as ddgs:
            # specifically use .news() for news search
            if do_news:
                results = list(ddgs.news(query, max_results=max_results))
            else:
                results = list(ddgs.text(query, max_results=max_results))

        if not results:
            print("No search results found with any method. Please check your internet connection or query.")
            return

        for idx, result in enumerate(results):
            # DDGS news results use 'url' key, text results use 'href'
            url = result.get('url') or result.get('href')
            if not url: continue

            print(f"\n[{idx+1}/{len(results)}] Processing: {url}")

            try:
                try:
                    driver.get(url)
                except TimeoutException:
                    print(f"Wait timeout reached for {url}, proceeding with available content...")

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
                if len(query) < 4: continue # Skip short words
                matches = process_ocr_and_crop(
                    screenshot_path,
                    query,
                    prefix=f"site_{idx}_{query.replace(' ', '_')}",
                    max_crops=max_crops_per_link
                )
                total_matches += matches

                print(f"Finished processing site {idx}. Total matches found: {total_matches}")

            except Exception as e:
                print(f"Error processing {url}: {e}")
                continue

    except Exception as e:
        print(f"An error occurred during search or initialization: {e}")
    finally:
        print("Cleaning up driver...")
        driver.quit()

if __name__ == "__main__":
    main()