import logging
import time
import base64
from undetected_chromedriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

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
        "format": "jpeg",
        "quality": 80,
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

def get_site_mode(driver: Chrome) -> str:
    """Detects if the site is dark mode or light mode based on background luminance."""
    script = """
    function getLuminance() {
        let bg = window.getComputedStyle(document.body).backgroundColor;
        if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') {
            bg = window.getComputedStyle(document.documentElement).backgroundColor;
        }
        
        let rgb = bg.match(/\\d+/g);
        if (!rgb || rgb.length < 3) return 255; // Default to light if we can't detect
        
        // standard luminance formula
        return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]);
    }
    return getLuminance();
    """
    try:
        luminance = driver.execute_script(script)
        # Luminance > 128 is generally considered 'light'
        return "light" if luminance > 128 else "dark"
    except Exception as e:
        logging.error(f"Failed to detect site mode: {e}")
        return "light" # Default fallback
