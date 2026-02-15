import sys
import logging
import tkinter as tk
from tkinter import messagebox
import core.utils as utils
import core.scraper as scraper
import gui

def main() -> None:
    # Configure logging for CLI usage (GUI will override/add handler)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Pre-check Tesseract
    if not utils.check_tesseract():
        error_msg = "Tesseract OCR not found. Please install it first"
        logging.error(error_msg)
        
        # If running without args (likely GUI mode or double-click), show alert
        if len(sys.argv) == 1:
            try:
                # Create a hidden root window just to show the error
                root = tk.Tk()
                root.withdraw() 
                messagebox.showerror("Tesseract Not Found", error_msg)
                root.destroy()
            except Exception:
                pass # If tk fails, we at least logged it
        
        sys.exit(1)

    if not utils.check_chrome():
        error_msg = "Chrome not found. Please install it first"
        logging.error(error_msg)
        
        # If running without args (likely GUI mode or double-click), show alert
        if len(sys.argv) == 1:
            try:
                # Create a hidden root window just to show the error
                root = tk.Tk()
                root.withdraw() 
                messagebox.showerror("Chrome Not Found", error_msg)
                root.destroy()
            except Exception:
                pass # If tk fails, we at least logged it
        
        sys.exit(1)

    # Check if arguments are provided
    if len(sys.argv) > 1:
        args = utils.parse_args()
        scraper.run_scraper(args)
    else:
        # GUI Mode
        # Setup queue handler for logging
        handler = gui.QueueHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

        root = tk.Tk()
        app = gui.GuiApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()
