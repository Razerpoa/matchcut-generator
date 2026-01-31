# Matchcut Generator

This tool automates the most tedious task when making a matchcut clip by automatically taking screenshot of various website and scan for the words using OCR and then crop it with an adjustable padding.

## Features

- CDP Full-Page Capture: Uses Chrome DevTools Protocol to capture high-resolution screenshots of the entire page content, bypassing standard scroll limitations.
- Smart Popup Handling: Automatically detects and dismisses common popups like consent bars and notification prompts using text analysis, JavaScript, and keyboard interactions.
- OCR-Based Cropping: Utilizes Tesseract OCR to locate specific keywords and crops the image around them with dynamic padding.
- Undetected Automation: Built on undetected-chromedriver to mimic human behavior and avoid automated browser detection.
- Content Loading: Includes logic to scroll and trigger lazy-loaded images or other dynamic content before capturing.

## Prerequisites

- Python 3.12 or higher
- Google Chrome (google-chrome-stable)
- Tesseract OCR:
  - Linux: sudo apt install tesseract-ocr
  - macOS: brew install tesseract
  - Windows: Download binaries from the Tesseract GitHub wiki
- uv (Recommended for dependency management)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Razerpoa/matchcut-generator.git
   cd matchcut-generator
   ```

2. Sync the dependencies:
   ```bash
   uv sync
   ```

## Usage

The script now supports command-line arguments for easier configuration.

Run the generator with default settings:
```bash
uv run main.py
```

Run with custom queries and options:
```bash
uv run main.py --search-query "Lionel Messi" --ocr-query "Messi" --remove-screenshots
```

### Arguments

- `--search-query`: The query to search on DuckDuckGo (default: "Cristiano Ronaldo").
- `--ocr-query`: The specific text to look for in screenshots via OCR (default: "Cristiano Ronaldo").
- `--remove-screenshots`: If provided, the full screenshot files will be deleted after processing to save space.
- `--max-results`: The number of search results to process (default: 5).

## Project Structure

- main.py: Core logic for automation, screenshotting, and OCR.
- crops/: Directory where extracted image segments are saved.
- pyproject.toml: Dependency and project configuration.
- .gitignore: Configured to ignore generated images and local environment files.

## Configuration

- Confidence Threshold: You can adjust OCR sensitivity by modifying the confidence check in main.py.
- Padding: Change the `pad` variable in main.py to adjust how much context is included around detected matches.
- Window Size: Set your preferred resolution in the ChromeOptions within main.py.
