# Matchcut Generator

This tool makes the clips for a Text Matchcut Video. After you run the tool you can start making the Matchcut on your favorite editing software.

## Features

- CDP Full-Page Capture: Uses Chrome DevTools Protocol to capture high-resolution screenshots of the entire page content, bypassing standard scroll limitations.
- Smart Popup Handling: Automatically detects and dismisses common popups like consent bars and notification prompts using text analysis, JavaScript, and keyboard interactions.
- OCR-Based Cropping: Utilizes Tesseract OCR to locate specific keywords and crops the image around them with dynamic padding.
- Undetected Automation: Built on undetected-chromedriver to mimic human behavior. Runs in headless mode by default.
- Content Loading: Includes logic to scroll and trigger lazy-loaded images or other dynamic content before capturing.

## Prerequisites

- Python 3.12 or higher
- Google Chrome
- Tesseract OCR:
  - Ubuntu/Debian: sudo apt install tesseract-ocr
  - Arch Linux: sudo pacman -S tesseract
  - macOS: brew install tesseract
  - Windows: Download and install [The Tesseract Installer](https://github.com/UB-Mannheim/tesseract/wiki).
    - Ensure it is installed and added to PATH.
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

The tool can be run in two modes: **GUI Mode** (User Interface) and **CLI Mode** (Command Line).

### GUI Mode
Simply run the script without any arguments to launch the graphical user interface:
```bash
uv run main.py
```
This will open a window where you can setting up:
- **Search Query**: What to search for on DuckDuckGo.
- **OCR Query**: The text to find and crop in the screenshots.
- **Max Results**: Number of websites into scrape.
- **Keep Screenshots**: Checkbox to save the full page screenshots.
- **Show Browser**: Checkbox to see the browser in action (useful for debugging).
- **Max Crops**: Limit crops per website.

### CLI Mode
You can also run it purely from the command line for automation or scripts:

The help command:
```bash
uv run main.py --help
```

Run with custom queries and options:
```bash
uv run main.py --search-query "Lionel Messi" --ocr-query "Messi"
```

To keep the full screenshots, use the `--keep-screenshots` flag:
```bash
uv run main.py --search-query "Lionel Messi" --ocr-query "Messi" --keep-screenshots
```

### Arguments

- `-s`, `--search-query`: The query to search on DuckDuckGo.
- `-o`, `--ocr-query`: The specific text to look for in screenshots via OCR.
- `-k`, `--keep-screenshots`: If provided, the full screenshot files will be kept. By default, they are removed after processing.
- `-sb`, `--show-browser`: If provided, the browser window will be visible. By default, it runs in headless mode.
- `-m`, `--max-results`: The number of search results to process (default: 5).
- `-mc`, `--max-crops-per-link`: The maximum number of crops to extract from a single webpage (default: 10).

## License

MIT [LICENSE](LICENSE)
