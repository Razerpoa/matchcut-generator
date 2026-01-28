# Matchcut Generator

A powerful tool to capture full-page screenshots of websites and automatically extract text segments using OCR. It features advanced popup handling and precision cropping for content extraction.

## 🚀 Features

- **CDP Full-Page Capture**: Uses Chrome DevTools Protocol to capture high-resolution screenshots of the entire page content, bypassing standard scroll limitations.
- **Smart Popup Handling**: Automatically detects and dismisses common popups (consent bars, "Lain kali" prompts) using text analysis, JavaScript, and keyboard interactions.
- **OCR-Based Cropping**: Utilizes Tesseract OCR to locate specific keywords and crops the image around them with dynamic padding for context.
- **Undetected Automation**: Built on `undetected-chromedriver` to mimic human behavior and avoid bot detection.
- **Optimized for Modern Web**: Includes smooth scrolling logic to trigger lazy-loaded images and dynamic content.

## 🛠️ Prerequisites

- **Python 3.12+**
- **Google Chrome**: Installed on your system (`google-chrome-stable`).
- **Tesseract OCR**: 
  - Linux: `sudo apt install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: [Download binaries](https://github.com/UB-Mannheim/tesseract/wiki)
- **uv**: Recommended for fast package management.

## 📥 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Razerpoa/matchcut-generator.git
   cd matchcut-generator
   ```

2. Sync dependencies:
   ```bash
   uv sync
   ```

## 📖 Usage

1. Open `main.py` and set your desired search term in the `query` variable:
   ```python
   query = "Your Keyword"
   ```

2. Run the generator:
   ```bash
   uv run main.py
   ```

3. View results:
   - `full_screenshot.png`: The complete webpage screenshot.
   - `crops/`: Individual images cropped around every instance of your keyword.

## 📂 Project Structure

- `main.py`: Core logic for automation, screenshotting, and OCR.
- `crops/`: Directory for outputted image segments.
- `pyproject.toml`: Dependency and project configuration.
- `.gitignore`: Configured to ignore generated images and local environments.

## ⚙️ Configuration

- **Confidence Threshold**: Adjust `int(data['conf'][i]) > 50` in `main.py` to change OCR sensitivity.
- **Padding**: Modify `pad = h * 4` to change how much context is included around matches.
- **Window Size**: Set in `options.add_argument("--window-size=1920,1080")`.
