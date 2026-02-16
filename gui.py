from core.utils import PAD_H_DEFAULT, PAD_W_DEFAULT
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import queue
import logging
import threading
import argparse
import os
import time

import core.scraper as scraper
from core.video import VideoGenerator

# Global queue for logging and callback for tqdm
log_queue = queue.Queue()
_GLOBAL_PROGRESS_CALLBACK = None

import tqdm
original_tqdm = tqdm.tqdm

class TqdmToGui(original_tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_gui_update = 0

    def update(self, n=1):
        super().update(n)
        if _GLOBAL_PROGRESS_CALLBACK:
            # Throttle updates to avoid flickering
            current_time = time.time()
            if current_time - self._last_gui_update > 0.1 or self.n == self.total:
                total = self.total if self.total else (self.n + 1)
                _GLOBAL_PROGRESS_CALLBACK(self.n, total, f"{self.desc or 'Processing'}: {self.n}/{self.total or '?'}")
                self._last_gui_update = current_time

    def close(self):
        if _GLOBAL_PROGRESS_CALLBACK and self.total:
            _GLOBAL_PROGRESS_CALLBACK(self.total, self.total, f"{self.desc or 'Done'}")
        super().close()

# Apply monkeypatch
tqdm.tqdm = TqdmToGui
tqdm.trange = lambda *args, **kwargs: TqdmToGui(range(*args), **kwargs)

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_queue.put(self.format(record))

class GuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Matchcut Generator GUI")
        self.root.geometry("700x750")

        self.style = ttk.Style()
        self.style.theme_use('clam') # Use a more modern theme
        
        # Configure some basic styles for "Rich Aesthetics"
        self.style.configure("TNotebook", background="#f0f0f0")
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabelframe", background="#f0f0f0")
        self.style.configure("TLabelframe.Label", background="#f0f0f0", font=('Helvetica', 10, 'bold'))
        self.style.configure("TButton", font=('Helvetica', 10))
        self.style.configure("Run.TButton", font=('Helvetica', 10, 'bold'), foreground="white", background="#007bff")
        self.style.map("Run.TButton", background=[('active', '#0056b3')])

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.scraper_tab = ttk.Frame(self.notebook)
        self.video_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.scraper_tab, text=" Scraper ")
        self.notebook.add(self.video_tab, text=" Combine Crops ")

        self.create_scraper_widgets()
        self.create_video_widgets()
        
        # Common elements (Progress and Logs)
        self.create_common_widgets()

        global _GLOBAL_PROGRESS_CALLBACK
        _GLOBAL_PROGRESS_CALLBACK = self.progress_callback

        self.root.after(100, self.poll_log_queue)

    def create_scraper_widgets(self):
        # Input Frame
        input_frame = ttk.LabelFrame(self.scraper_tab, text="Scraper Configuration", padding="15")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        # Search Query
        ttk.Label(input_frame, text="Search Query:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.search_query_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.search_query_var, width=50).grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # OCR Query
        ttk.Label(input_frame, text="OCR Query:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.ocr_query_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.ocr_query_var, width=50).grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        # Grid for smaller inputs
        grid_frame = ttk.Frame(input_frame)
        grid_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=10)

        # Max Results
        ttk.Label(grid_frame, text="Max Results:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.max_results_var = tk.IntVar(value=5)
        ttk.Spinbox(grid_frame, from_=1, to=100, textvariable=self.max_results_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)

        # Max Crops Per Link
        ttk.Label(grid_frame, text="Max Crops/Link:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        self.max_crops_var = tk.IntVar(value=10)
        ttk.Spinbox(grid_frame, from_=1, to=50, textvariable=self.max_crops_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)

        # Chrome Version
        ttk.Label(grid_frame, text="Chrome Version:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.chrome_version_var = tk.IntVar(value=144)
        ttk.Entry(grid_frame, textvariable=self.chrome_version_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)

        # Padding Settings
        ttk.Label(grid_frame, text="Padding H:").grid(row=1, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        self.pad_h_var = tk.DoubleVar(value=PAD_H_DEFAULT)
        ttk.Entry(grid_frame, textvariable=self.pad_h_var, width=10).grid(row=1, column=3, sticky=tk.W, pady=2, padx=5)

        ttk.Label(grid_frame, text="Padding W:").grid(row=2, column=2, sticky=tk.W, pady=2, padx=(10, 0))
        self.pad_w_var = tk.DoubleVar(value=PAD_W_DEFAULT)
        ttk.Entry(grid_frame, textvariable=self.pad_w_var, width=10).grid(row=2, column=3, sticky=tk.W, pady=2, padx=5)

        # Chrome Path
        ttk.Label(input_frame, text="Chrome Path (Opt):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.chrome_path_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.chrome_path_var, width=50).grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)

        # Checkboxes
        check_frame = ttk.Frame(input_frame)
        check_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        self.keep_screenshots_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(check_frame, text="Keep Screenshots", variable=self.keep_screenshots_var).pack(side=tk.LEFT, padx=5)

        self.show_browser_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(check_frame, text="Show Browser", variable=self.show_browser_var).pack(side=tk.LEFT, padx=5)

        self.invert_mismatched_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(check_frame, text="Invert Mismatched Sites", variable=self.invert_mismatched_var).pack(side=tk.LEFT, padx=5)

        self.bw_mismatched_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(check_frame, text="B&W Mismatched Sites", variable=self.bw_mismatched_var).pack(side=tk.LEFT, padx=5)

        # Site Mode Preference
        ttk.Label(input_frame, text="Site Mode:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.site_mode_var = tk.StringVar(value="any")
        self.site_mode_dropdown = ttk.Combobox(input_frame, textvariable=self.site_mode_var, values=["any", "dark", "light"], state="readonly", width=10)
        self.site_mode_dropdown.grid(row=5, column=1, sticky=tk.W, pady=5, padx=5)

        # Run Button
        self.run_scraper_btn = ttk.Button(self.scraper_tab, text="START SCRAPER", style="Run.TButton", command=self.start_scraping)
        self.run_scraper_btn.pack(pady=10)

    def create_video_widgets(self):
        # Video Config Frame
        video_frame = ttk.LabelFrame(self.video_tab, text="Video Generation Settings", padding="15")
        video_frame.pack(fill=tk.X, padx=10, pady=10)

        # Resolution
        ttk.Label(video_frame, text="Resolution:").grid(row=0, column=0, sticky=tk.W, pady=5)
        res_frame = ttk.Frame(video_frame)
        res_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        self.vid_width_var = tk.IntVar(value=1080)
        ttk.Entry(res_frame, textvariable=self.vid_width_var, width=8).pack(side=tk.LEFT)
        ttk.Label(res_frame, text="x").pack(side=tk.LEFT, padx=5)
        self.vid_height_var = tk.IntVar(value=1080)
        ttk.Entry(res_frame, textvariable=self.vid_height_var, width=8).pack(side=tk.LEFT)

        # Clip Duration
        ttk.Label(video_frame, text="Clip Duration (Frames):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.vid_duration_var = tk.IntVar(value=2)
        ttk.Spinbox(video_frame, from_=1, to=120, textvariable=self.vid_duration_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

        # Audio Settings
        ttk.Label(video_frame, text="Audio:").grid(row=2, column=0, sticky=tk.W, pady=5)
        audio_subframe = ttk.Frame(video_frame)
        audio_subframe.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        self.use_audio_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(audio_subframe, text="Enable Transition Audio", variable=self.use_audio_var).pack(side=tk.LEFT)
        
        # Audio File Chooser
        ttk.Label(video_frame, text="Custom Audio:").grid(row=3, column=0, sticky=tk.W, pady=5)
        audio_path_frame = ttk.Frame(video_frame)
        audio_path_frame.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        self.custom_audio_var = tk.StringVar()
        ttk.Entry(audio_path_frame, textvariable=self.custom_audio_var, width=40).pack(side=tk.LEFT)
        ttk.Button(audio_path_frame, text="Browse", command=self.browse_audio).pack(side=tk.LEFT, padx=5)

        # Generation Options
        self.shuffle_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(video_frame, text="Shuffle Clips", variable=self.shuffle_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Generate Button
        self.gen_video_btn = ttk.Button(self.video_tab, text="GENERATE VIDEO", style="Run.TButton", command=self.start_video_generation)
        self.gen_video_btn.pack(pady=20)

    def create_common_widgets(self):
        # Progress Bar and Status
        progress_frame = ttk.Frame(self.root, padding="10")
        progress_frame.pack(fill=tk.X, padx=10)
        
        self.status_label = ttk.Label(progress_frame, text="Ready", font=('Helvetica', 9, 'italic'))
        self.status_label.pack(anchor=tk.W)
        
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, pady=5)

        # Logs
        log_frame = ttk.LabelFrame(self.root, text="System Logs", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=('Consolas', 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def browse_audio(self):
        filename = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.ogg")])
        if filename:
            self.custom_audio_var.set(filename)

    def start_scraping(self):
        search = self.search_query_var.get()
        ocr = self.ocr_query_var.get()
        
        if not search or not ocr:
            messagebox.showerror("Error", "Search Query and OCR Query are required!")
            return

        if len(ocr) < 4:
            messagebox.showwarning("Warning", "OCR Query must be at least 4 characters long.")
            return

        self.run_scraper_btn.config(state='disabled')
        self.gen_video_btn.config(state='disabled')
        self.log_area.config(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state='disabled')
        self.progress['value'] = 0
        self.status_label.config(text="Starting Scraper...")

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
            pad_w=self.pad_w_var.get(),
            site_mode=self.site_mode_var.get(),
            invert_mismatched=self.invert_mismatched_var.get(),
            bw_mismatched=self.bw_mismatched_var.get()
        )

        threading.Thread(target=self.run_scraper_thread, args=(args,), daemon=True).start()

    def run_scraper_thread(self, args):
        scraper.run_scraper(args, self.progress_callback)
        self.root.after(0, self.finish_task, "Scraping Completed!")

    def start_video_generation(self):
        if not os.path.exists("crops") or not os.listdir("crops"):
             messagebox.showerror("Error", "No crops found in 'crops/' folder. Run the scraper first!")
             return

        self.run_scraper_btn.config(state='disabled')
        self.gen_video_btn.config(state='disabled')
        self.progress['value'] = 0
        self.status_label.config(text="Preparing video generation...")

        params = {
            'width': self.vid_width_var.get(),
            'height': self.vid_height_var.get(),
            'frame_duration': self.vid_duration_var.get(),
            'use_audio': self.use_audio_var.get(),
            'custom_audio_path': self.custom_audio_var.get(),
            'shuffle': self.shuffle_var.get()
        }

        threading.Thread(target=self.run_video_thread, args=(params,), daemon=True).start()

    def run_video_thread(self, params):
        vg = VideoGenerator()
        try:
            output_path = vg.combine_crops_to_video(
                width=params['width'],
                height=params['height'],
                frame_duration=params['frame_duration'],
                use_audio=params['use_audio'],
                custom_audio_path=params['custom_audio_path'],
                shuffle=params['shuffle'],
                progress_callback=self.progress_callback
            )
            if output_path:
                logging.info(f"Video saved to: {output_path}")
                self.root.after(0, self.finish_task, f"Video Generated: {output_path}")
            else:
                self.root.after(0, self.finish_task, "Video generation failed (no clips).")
        except Exception as e:
            logging.error(f"Error generating video: {e}")
            self.root.after(0, self.finish_task, f"Error: {e}")

    def progress_callback(self, current, total, message):
         self.root.after(0, lambda: self.update_progress(current, total, message))

    def update_progress(self, current, total, message):
        if total > 0:
            self.progress['value'] = (current / total) * 100
        self.status_label.config(text=message)

    def finish_task(self, message):
        self.run_scraper_btn.config(state='normal')
        self.gen_video_btn.config(state='normal')
        self.status_label.config(text="Ready")
        messagebox.showinfo("Info", message)

    def poll_log_queue(self):
        while not log_queue.empty():
            msg = log_queue.get()
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, msg + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(100, self.poll_log_queue)
