import time
import os
import base64
import numpy as np
import pytesseract
from PIL import Image
from undetected_chromedriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

def get_full_page_screenshot(driver, path):
    """Uses Chrome DevTools Protocol to capture the entire page length."""
    print("Capturing full page screenshot via CDP...")
    # Get the metrics of the page
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    width = metrics['contentSize']['width']
    height = metrics['contentSize']['height']

    # Force the viewport to encompass the whole page
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": width,
        "height": height,
        "deviceScaleFactor": 1,
        "mobile": False
    })

    screenshot_data = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "format": "png",
        "fromSurface": True,
        "captureBeyondViewport": True
    })
    
    with open(path, "wb") as f:
        f.write(base64.b64decode(screenshot_data['data']))
    
    # Reset device override to avoid breaking subsequent scripts
    driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
    print(f"Full page screenshot saved to {path}")

def handle_popups(driver):
    wait = WebDriverWait(driver, 5)
    
    # 1. Target the specific "Lain kali" button by text and attributes
    # We use a broader XPath to find the text even if it's inside a nested span
    dismiss_keywords = ["Lain kali", "Not now", "No thanks"]
    
    for text in dismiss_keywords:
        try:
            # This XPath looks for any clickable element containing the text
            element = driver.find_element(By.XPATH, f"//*[contains(text(), '{text}')]")
            if element.is_displayed():
                # Trick: Use ActionChains to move and click to bypass "overlay" errors
                ActionChains(driver).move_to_element(element).click().perform()
                print(f"Dismissed popup using text: {text}")
                time.sleep(1)
                return
        except:
            continue

    # 2. Try clicking by JavaScript (if standard click is intercepted)
    try:
        # Google often uses a specific structure for these buttons. 
        # This JS snippet finds buttons with the text 'Lain kali' and clicks them directly.
        driver.execute_script("""
            var buttons = document.querySelectorAll('button, div[role="button"]');
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].innerText.includes('Lain kali')) {
                    buttons[i].click();
                }
            }
        """)
    except Exception as e:
        print(f"JS click failed: {e}")

    # 3. Final Boss: The Escape Key
    # Sometimes just hitting 'Escape' triggers the 'Lain kali' logic on these overlays
    try:
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    except:
        pass

def process_ocr_and_crop(image_path, search_text, output_dir="crops"):
    """OCR search with confidence filtering and padding."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    img = Image.open(image_path)
    # --psm 11: Sparse text. Finds as much text as possible in no particular order.
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config='--psm 11')
    
    found_count = 0
    for i in range(len(data['text'])):
        # Filter for confidence and text match
        if int(data['conf'][i]) > 50 and search_text.lower() in data['text'][i].lower():
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            
            # Dynamic padding (2x the height of the text for context)
            pad = h * 4
            left = max(0, x - pad)
            top = max(0, y - pad)
            right = min(img.width, x + w + pad)
            bottom = min(img.height, y + h + pad)
            
            crop_img = img.crop((left, top, right, bottom))
            crop_path = os.path.join(output_dir, f"match_{found_count}.png")
            crop_img.save(crop_path)
            print(f"Cropped instance {found_count} at ({x}, {y})")
            found_count += 1
            
    if found_count == 0:
        print(f"No reliable OCR matches for '{search_text}'.")

def main():
    options = ChromeOptions()
    # options.add_argument("--headless") # Headless is harder to detect with undetected_chromedriver
    options.add_argument("--window-size=1920,1080")
    
    driver = Chrome(options=options)
    query = "Fathan"
    screenshot_path = "full_screenshot.png"
    
    try:
        url = f"https://www.google.com/search?q={query}"
        driver.get(url)
        time.sleep(2) 
        
        handle_popups(driver)
        
        # Smooth scroll to trigger lazy loading if necessary
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")

        get_full_page_screenshot(driver, screenshot_path)
        process_ocr_and_crop(screenshot_path, query)
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()