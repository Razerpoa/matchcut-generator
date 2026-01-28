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

def preprocess_for_ocr(img):
    img = img.convert('L') # Grayscale
    img = ImageOps.autocontrast(img)
    # img = img.filter(ImageFilter.SHARPEN) # Optional: helps with small text
    return img

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

def process_ocr_and_crop(image_path, search_text, output_dir="crops", prefix="match", max_crops=10):
    """OCR search with confidence filtering and padding."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    img = Image.open(image_path)
    img = preprocess_for_ocr(img)
    # config='--psm 11' is for sparse text
    if os.name == 'nt':
        pytesseract.pytesseract.tesseract_cmd = r'C:\Users\lenovo\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'  # Update this path as needed
        
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config='--psm 11')

    found_count = 0
    for i in range(len(data['text'])):
        if found_count >= max_crops:
            break

        if int(data['conf'][i]) > 40 and search_text.lower() in data['text'][i].lower():
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]

            # Use a more balanced padding
            pad = h * 4
            left = max(0, x - pad)
            top = max(0, y - pad)
            right = min(img.width, x + w + pad)
            bottom = min(img.height, y + h + pad)

            crop_img = img.crop((left, top, right, bottom))
            crop_filename = f"{prefix.replace(' ', '_')}_{found_count}.png"
            crop_path = os.path.join(output_dir, crop_filename)
            crop_img.save(crop_path)
            print(f"Cropped match at ({x}, {y}) -> {crop_path}")
            found_count += 1

    if found_count == 0:
        print(f"No reliable OCR matches for '{search_text}' in {image_path}.")
    return found_count

def main():
    query = "Kelulusan"
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