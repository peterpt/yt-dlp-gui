import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import yt_dlp
import os
import threading
import json
import sys
import shutil
import webbrowser
from pydub import AudioSegment
import queue

# --- Class to redirect stdout/stderr to a GUI widget ---
class TextRedirector:
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, message):
        self.log_queue.put(message)

    def flush(self):
        pass

# --- Main Application Class ---
class YTDL_App:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube-DLP Downloader")
        self.root.geometry("800x650")
        
        # --- Class variables ---
        self.formats_data = {}
        self.config_file = "config.json"
        self.settings = {}
        self.debug_win = None
        
        # --- Setup log redirection ---
        self.log_queue = queue.Queue()
        sys.stdout = TextRedirector(self.log_queue)
        sys.stderr = TextRedirector(self.log_queue)
        self.root.after(100, self.process_log_queue)

        # --- Load settings and perform initial FFmpeg check ---
        self.load_settings()
        self.ffmpeg_path = self.check_ffmpeg()

        # --- Style Configuration ---
        style = ttk.Style(self.root)
        style.theme_use('clam')

        # --- Menu Bar ---
        self.create_menu()

        # --- Main Layout Frames ---
        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(fill=tk.X)
        title_frame = ttk.Frame(self.root, padding=(10, 0, 10, 5))
        title_frame.pack(fill=tk.X)
        list_frame = ttk.Frame(self.root, padding="10")
        list_frame.pack(expand=True, fill=tk.BOTH)
        location_frame = ttk.Frame(self.root, padding="10")
        location_frame.pack(fill=tk.X)
        action_frame = ttk.Frame(self.root, padding="10")
        action_frame.pack(fill=tk.X)
        
        # --- Widgets ---
        # ... (Input, Title, Listbox, and Location widgets are the same)
        ttk.Label(input_frame, text="Video/Audio URL:").pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(input_frame, width=60)
        self.url_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.make_right_click_menu(self.url_entry)
        self.fetch_button = ttk.Button(input_frame, text="Fetch Formats", command=self.start_fetch_thread)
        self.fetch_button.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(title_frame, text="Video Title:").pack(side=tk.LEFT)
        self.title_label = ttk.Label(title_frame, text="N/A", font=("Helvetica", 10, "bold"), wraplength=700)
        self.title_label.pack(side=tk.LEFT, padx=5)
        self.formats_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, font=("Courier", 10))
        self.formats_listbox.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.formats_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.formats_listbox.config(yscrollcommand=scrollbar.set)
        ttk.Label(location_frame, text="Save to:").pack(side=tk.LEFT, padx=(0, 5))
        self.location_entry = ttk.Entry(location_frame, width=50)
        self.location_entry.insert(0, os.getcwd())
        self.location_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.browse_button = ttk.Button(location_frame, text="Browse...", command=self.browse_location)
        self.browse_button.pack(side=tk.LEFT, padx=(5, 0))

        # --- MODIFIED: Action Frame Widgets for Progress Bar ---
        self.download_button = ttk.Button(action_frame, text="Download Selected", command=self.start_download_thread)
        self.download_button.pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(action_frame, orient='horizontal', mode='determinate')
        # The progress bar will be packed/unpacked as needed

        self.status_label = ttk.Label(action_frame, text="Enter a URL and click 'Fetch Formats'")
        self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X)

        if not self.ffmpeg_path:
            self.download_button.config(state=tk.DISABLED)
            self.update_status("FFmpeg not found. Please configure it in Settings or install it.")

    # --- Debug Window and Log Processing (Unchanged) ---
    def open_debug_window(self):
        if self.debug_win and self.debug_win.winfo_exists():
            self.debug_win.deiconify()
            self.debug_win.lift()
            return
        self.debug_win = tk.Toplevel(self.root)
        self.debug_win.title("Debug Log")
        self.debug_win.geometry("700x500")
        self.debug_text = scrolledtext.ScrolledText(self.debug_win, state='disabled', wrap=tk.WORD, font=("Courier", 9))
        self.debug_text.pack(expand=True, fill='both')
        self.debug_win.protocol("WM_DELETE_WINDOW", self.debug_win.withdraw)

    def process_log_queue(self):
        try:
            while not self.log_queue.empty():
                message = self.log_queue.get_nowait()
                if self.debug_win and self.debug_win.winfo_exists():
                    self.debug_text.config(state='normal')
                    self.debug_text.insert(tk.END, message)
                    self.debug_text.see(tk.END)
                    self.debug_text.config(state='disabled')
        finally:
            self.root.after(100, self.process_log_queue)
    
    # --- Other methods (Unchanged, except where noted) ---
    # ... (check_ffmpeg, handle_ffmpeg_not_found, make_right_click_menu, etc. are unchanged)
    def check_ffmpeg(self):
        saved_path = self.settings.get("ffmpeg_path")
        if saved_path and os.path.exists(saved_path):
            AudioSegment.converter = saved_path
            return saved_path
        executable = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        found_path = shutil.which(executable)
        if found_path:
            self.settings["ffmpeg_path"] = found_path
            self.save_settings()
            AudioSegment.converter = found_path
            return found_path
        else:
            self.handle_ffmpeg_not_found()
            return None
            
    def handle_ffmpeg_not_found(self):
        title = "FFmpeg Not Found"
        if sys.platform == "win32":
            message = ("FFmpeg is required for audio conversion and video merging.\n\n"
                       "Would you like to open the official download page now?\n\n"
                       "(After downloading, extract 'ffmpeg.exe' into the same folder as this application and restart it.)")
            if messagebox.askyesno(title, message):
                webbrowser.open("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")
        else:
            message = ("FFmpeg is required but could not be found in your PATH.\n\n"
                       "Please install it using your system's package manager.\n"
                       "Example for Debian/Ubuntu:\n"
                       "sudo apt install ffmpeg")
            messagebox.showerror(title, message)
        return

    def make_right_click_menu(self, widget):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def load_settings(self):
        try:
            with open(self.config_file, 'r') as f:
                self.settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.settings = {"audio_format": "mp3", "mp3_bitrate": "192k", "ffmpeg_path": ""}

    def save_settings(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.settings, f, indent=4)
            
    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Configure...", command=self.open_settings_window)
        view_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Show Debug Log", command=self.open_debug_window)

    def open_settings_window(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configuration")
        settings_win.transient(self.root)
        settings_win.grab_set()
        frame = ttk.Frame(settings_win, padding="20")
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="Audio Conversion Format:").grid(row=0, column=0, sticky="w", pady=5)
        audio_format_var = tk.StringVar(value=self.settings.get("audio_format", "mp3"))
        audio_format_combo = ttk.Combobox(frame, textvariable=audio_format_var, values=["mp3", "flac", "Keep Original"])
        audio_format_combo.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(frame, text="MP3 Bitrate (if converting):").grid(row=1, column=0, sticky="w", pady=5)
        mp3_bitrate_var = tk.StringVar(value=self.settings.get("mp3_bitrate", "192k"))
        mp3_bitrate_combo = ttk.Combobox(frame, textvariable=mp3_bitrate_var, values=["128k", "192k", "256k", "320k"])
        mp3_bitrate_combo.grid(row=1, column=1, sticky="ew", padx=5)
        def save_and_close():
            self.settings["audio_format"] = audio_format_var.get()
            self.settings["mp3_bitrate"] = mp3_bitrate_var.get()
            self.save_settings()
            messagebox.showinfo("Saved", "Settings have been saved.", parent=settings_win)
            settings_win.destroy()
        save_button = ttk.Button(frame, text="Save", command=save_and_close)
        save_button.grid(row=3, column=0, pady=20)
        cancel_button = ttk.Button(frame, text="Cancel", command=settings_win.destroy)
        cancel_button.grid(row=3, column=1, pady=20)
    
    def browse_location(self):
        directory = filedialog.askdirectory()
        if directory:
            self.location_entry.delete(0, tk.END)
            self.location_entry.insert(0, directory)

    def update_status(self, message):
        self.status_label.config(text=message)

    # --- NEW: Method to safely update the progress bar from any thread ---
    def update_progress(self, value):
        self.progress_bar['value'] = value

    def start_fetch_thread(self):
        # ... (Unchanged)
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return
        self.fetch_button.config(state=tk.DISABLED)
        self.download_button.config(state=tk.DISABLED if not self.ffmpeg_path else tk.NORMAL)
        self.title_label.config(text="Fetching...")
        self.formats_listbox.delete(0, tk.END)
        self.update_status("Fetching formats... Please wait.")
        threading.Thread(target=self.get_formats, args=(url,)).start()

    def get_formats(self, url):
        # ... (Unchanged)
        try:
            with yt_dlp.YoutubeDL({'quiet': False}) as ydl:
                info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'No title found')
            self.title_label.config(text=video_title)
            self.formats_data.clear()
            for f in info.get('formats', []):
                if f.get('ext') == 'mhtml': continue
                filesize_mb = f"{(f.get('filesize') or f.get('filesize_approx', 0)) / (1024*1024):.2f} MB"
                resolution = f.get('resolution', 'audio only')
                vcodec = "video only" if f.get('vcodec') != 'none' and f.get('acodec') == 'none' else f.get('vcodec', 'none')
                acodec = "audio only" if f.get('acodec') != 'none' and f.get('vcodec') == 'none' else f.get('acodec', 'none')
                format_string = f"{f['format_id']:<10} | {f['ext']:<8} | {resolution:<15} | {filesize_mb:<15} | {vcodec} | {acodec}"
                self.formats_listbox.insert(tk.END, format_string)
                self.formats_data[format_string] = f
            self.update_status("Formats loaded. Select one and click Download.")
        except Exception as e:
            self.title_label.config(text="Failed to fetch title")
            print(f"ERROR: Failed to fetch formats: {e}")
            messagebox.showerror("Error", f"Failed to fetch formats. See debug log for details.")
            self.update_status("Error fetching formats.")
        finally:
            self.fetch_button.config(state=tk.NORMAL)
            if self.ffmpeg_path: self.download_button.config(state=tk.NORMAL)


    def start_download_thread(self):
        # ... (Largely unchanged, but now shows the progress bar)
        if not self.formats_listbox.curselection():
            messagebox.showerror("Error", "Please select a format to download.")
            return
        selected_str = self.formats_listbox.get(self.formats_listbox.curselection())
        format_info = self.formats_data.get(selected_str)
        if not format_info:
            messagebox.showerror("Error", "Could not find format details.")
            return
        
        # --- MODIFIED: Show and reset the progress bar ---
        self.progress_bar['value'] = 0
        self.progress_bar.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
        
        self.fetch_button.config(state=tk.DISABLED)
        self.download_button.config(state=tk.DISABLED)
        threading.Thread(target=self.process_download, args=(format_info,)).start()

    def process_download(self, format_info):
        url = self.url_entry.get()
        location = self.location_entry.get()
        is_video = format_info.get('vcodec', 'none') != 'none'
        is_audio_only = not is_video and format_info.get('acodec', 'none') != 'none'
        
        # --- MODIFIED: Use the new combined hook ---
        ydl_opts = {'noplaylist': True, 'progress_hooks': [self.download_hook]}
        
        try:
            # ... (Download logic is the same)
            if is_video:
                self.update_status("Downloading video with best audio...")
                ydl_opts['format'] = f"{format_info['format_id']}+bestaudio"
                ydl_opts['outtmpl'] = os.path.join(location, '%(title)s.%(ext)s')
                ydl_opts['merge_output_format'] = 'mp4'
            elif is_audio_only:
                self.update_status("Downloading audio...")
                ydl_opts['format'] = format_info['format_id']
                ydl_opts['outtmpl'] = os.path.join(location, '%(title)s.%(ext)s')
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
            if is_audio_only and self.settings['audio_format'] != 'Keep Original':
                self.convert_audio(downloaded_file)
            else:
                self.update_status("Download complete!")
                messagebox.showinfo("Success", f"File successfully downloaded to:\n{downloaded_file}")
        except Exception as e:
            print(f"DOWNLOAD ERROR: {e}")
            messagebox.showerror("Download Error", f"An error occurred. See debug log for details.")
            self.update_status(f"Download failed.")
        finally:
            self.fetch_button.config(state=tk.NORMAL)
            if self.ffmpeg_path: self.download_button.config(state=tk.NORMAL)
            # --- MODIFIED: Hide the progress bar on completion/failure ---
            self.root.after(0, self.progress_bar.pack_forget)

    def convert_audio(self, filepath):
        # ... (Unchanged)
        convert_format = self.settings['audio_format']
        bitrate = self.settings.get('mp3_bitrate')
        self.update_status(f"Converting to {convert_format}...")
        try:
            audio = AudioSegment.from_file(filepath)
            new_filepath = os.path.splitext(filepath)[0] + f'.{convert_format}'
            export_params = {'format': convert_format}
            if convert_format == 'mp3' and bitrate:
                export_params['bitrate'] = bitrate
            audio.export(new_filepath, **export_params)
            os.remove(filepath)
            self.update_status(f"Successfully converted to {new_filepath}")
            messagebox.showinfo("Success", f"File converted to:\n{new_filepath}")
        except Exception as e:
            print(f"CONVERSION ERROR: {e}")
            messagebox.showerror("Conversion Error", f"Failed to convert: {e}\nEnsure FFmpeg is installed and configured.")
            self.update_status("Conversion failed.")


    # --- MODIFIED: New comprehensive download hook ---
    def download_hook(self, d):
        if d['status'] == 'downloading':
            # Get progress details
            total_bytes = d.get('total_bytes') or d.get('total_bytes_est')
            downloaded_bytes = d.get('downloaded_bytes')
            speed = d.get('_speed_str', 'N/A').strip()
            
            if total_bytes and downloaded_bytes:
                # Calculate percentage
                percentage = (downloaded_bytes / total_bytes) * 100
                
                # Update GUI components safely
                self.root.after(0, self.update_progress, percentage)
                self.root.after(0, self.update_status, f"Downloading: {percentage:.1f}% at {speed}")

        elif d['status'] == 'finished':
            # Ensure progress bar reaches 100% and update status
            self.root.after(0, self.update_progress, 100)
            self.root.after(0, self.update_status, "Download finished. Merging/Processing...")
        
        elif d['status'] == 'error':
            self.root.after(0, self.update_status, "An error occurred during download.")

# --- Run the App ---
if __name__ == "__main__":
    root = tk.Tk()
    app = YTDL_App(root)
    root.mainloop()
