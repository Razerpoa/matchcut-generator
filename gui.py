import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import queue
import logging
import threading
import argparse

import core.scraper as scraper

# Global queue for logging
log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_queue.put(self.format(record))

class GuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Matchcut Generator GUI")
        self.root.geometry("600x750")

        self.create_widgets()
        self.root.after(100, self.poll_log_queue)

    def create_widgets(self):
        # Input Frame
        input_frame = ttk.LabelFrame(self.root, text="Configuration", padding="10")
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # Search Query
        ttk.Label(input_frame, text="Search Query:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.search_query_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.search_query_var, width=50).grid(row=0, column=1, sticky=tk.W, pady=2)

        # OCR Query
        ttk.Label(input_frame, text="OCR Query:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.ocr_query_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.ocr_query_var, width=50).grid(row=1, column=1, sticky=tk.W, pady=2)

        # Max Results
        ttk.Label(input_frame, text="Max Results:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_results_var = tk.IntVar(value=5)
        ttk.Spinbox(input_frame, from_=1, to=100, textvariable=self.max_results_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=2)

        # Max Crops Per Link
        ttk.Label(input_frame, text="Max Crops/Link:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.max_crops_var = tk.IntVar(value=10)
        ttk.Spinbox(input_frame, from_=1, to=50, textvariable=self.max_crops_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=2)

        # Chrome Version
        ttk.Label(input_frame, text="Chrome Version:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.chrome_version_var = tk.IntVar(value=144)
        ttk.Entry(input_frame, textvariable=self.chrome_version_var, width=10).grid(row=4, column=1, sticky=tk.W, pady=2)

        # Chrome Path
        ttk.Label(input_frame, text="Chrome Path (Optional):").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.chrome_path_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.chrome_path_var, width=50).grid(row=5, column=1, sticky=tk.W, pady=2)

        # Padding Settings
        ttk.Label(input_frame, text="Vertical Padding:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.pad_h_var = tk.DoubleVar(value=5.0)
        ttk.Entry(input_frame, textvariable=self.pad_h_var, width=10).grid(row=6, column=1, sticky=tk.W, pady=2)

        ttk.Label(input_frame, text="Horizontal Padding:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.pad_w_var = tk.DoubleVar(value=1.0)
        ttk.Entry(input_frame, textvariable=self.pad_w_var, width=10).grid(row=7, column=1, sticky=tk.W, pady=2)

        # Checkboxes
        self.keep_screenshots_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(input_frame, text="Keep Screenshots", variable=self.keep_screenshots_var).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=2)

        self.show_browser_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(input_frame, text="Show Browser", variable=self.show_browser_var).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=2)

        # Run Button
        self.run_btn = ttk.Button(self.root, text="Run Scraper", command=self.start_scraping)
        self.run_btn.pack(pady=10)
        
        # Progress Bar and Status
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(anchor=tk.W)
        
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

        # Logs
        log_frame = ttk.LabelFrame(self.root, text="Logs", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def start_scraping(self):
        search = self.search_query_var.get()
        ocr = self.ocr_query_var.get()
        
        if not search or not ocr:
            messagebox.showerror("Error", "Search Query and OCR Query are required!")
            return

        if len(ocr) < 4:
            messagebox.showwarning("Warning", "OCR Query must be at least 4 characters long.")
            return

        self.run_btn.config(state='disabled')
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        self.progress['value'] = 0
        self.status_label.config(text="Starting...")

        args = argparse.Namespace(
            search_query=search,
            ocr_query=ocr,
            keep_screenshots=self.keep_screenshots_var.get(),
            max_results=self.max_results_var.get(),
            chrome_version=self.chrome_version_var.get(),
            show_browser=self.show_browser_var.get(),
            max_crops_per_link=self.max_crops_var.get(),
            chrome_path=self.chrome_path_var.get(),
            pad_h=self.pad_h_var.get(),
            pad_w=self.pad_w_var.get()
        )

        threading.Thread(target=self.run_thread, args=(args,), daemon=True).start()

    def run_thread(self, args):
        scraper.run_scraper(args, self.progress_callback)
        self.root.after(0, self.finish_scraping)
        
    def progress_callback(self, current, total, message):
         self.root.after(0, lambda: self.update_progress(current, total, message))

    def update_progress(self, current, total, message):
        if total > 0:
            self.progress['value'] = (current / total) * 100
        self.status_label.config(text=message)

    def finish_scraping(self):
        self.run_btn.config(state='normal')
        self.status_label.config(text="Finished")
        messagebox.showinfo("Info", "Scraping Completed!")

    def poll_log_queue(self):
        while not log_queue.empty():
            msg = log_queue.get()
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, msg + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(100, self.poll_log_queue)
