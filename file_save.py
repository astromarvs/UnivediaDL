import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from urllib.parse import urlparse
import yt_dlp
import re, os, sys
import subprocess
import instaloader
import platform
from PIL import Image, ImageTk
import os


from downloader import download_facebook, download_tiktok, download_youtube, download_instagram_videos, download_instagram_images

def resource_path(filename):
    """Get absolute path to resource, works in dev and exe"""
    try:
        base_path = sys._MEIPASS  # PyInstaller sets this in --onefile mode
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)

def sanitize_youtube_url(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        # Remove playlist parameters (&list=...) but keep video id
        url = re.sub(r"&list=[^&]+", "", url)
        url = re.sub(r"\?list=[^&]+", "", url)  # If it's only a list parameter
        # Clean trailing ? or & if empty
        url = url.rstrip("?&")
    return url

# Utility to load and optionally tilt icons
def load_icon(path, size=None, angle=0):
    img = Image.open(path)
    if angle != 0:
        img = img.rotate(angle, expand=True)
    if size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img)


def main_window():
    def is_valid_url(url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url.strip())
        return bool(parsed.scheme and parsed.netloc)

    def strip_ansi(text):
        return re.sub(r'\x1b\[[0-9;]*[mK]', '', text)

    def log_callback(msg):
        clean_msg = strip_ansi(msg)
        progress_text.configure(state='normal')
        progress_text.insert(tk.END, clean_msg + '\n')
        progress_text.see(tk.END)
        progress_text.configure(state='disabled')

    def clear_logs():
        progress_text.configure(state='normal')
        progress_text.delete(1.0, tk.END)
        progress_text.configure(state='disabled')

    # --- Custom download completed box ---
    def show_download_completed_box(file_path):
        def open_file():
            try:
                if platform.system() == "Windows":
                    os.startfile(file_path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", file_path])
                else:
                    subprocess.Popen(["xdg-open", file_path])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
            clear_fields()
            top.destroy()

        def open_location():
            folder = os.path.dirname(file_path)
            try:
                if platform.system() == "Windows":
                    os.startfile(folder)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open folder: {e}")
            clear_fields()
            top.destroy()

        def ok_action():
            clear_fields()
            top.destroy()

        def clear_fields():
            nonlocal messagebox_shown
            messagebox_shown = False  # reset for next download
            url_entry.delete(0, tk.END)
            format_var.set('mp4')
            subtitle_var.set('none')
            subtitle_check_var.set(False)
            output_path_var.set('')
            progress_label.config(text="Enter a URL and click 'Check URL'")
            disable_download_fields()
            clear_logs()  # Clear logs when fields are cleared

        top = tk.Toplevel(root)
        top.title("Download Completed")
        top.geometry("500x150")
        top.grab_set()  # modal window
        top.resizable(False, False)
        
        # Center the window
        top.transient(root)
        top.geometry(f"500x150+{root.winfo_x()+root.winfo_width()//2-250}+{root.winfo_y()+root.winfo_height()//2-60}")

        ttk.Label(top, text="Download completed!", font=("Arial", 10, "bold")).pack(pady=(10, 5))

        # Read-only Textbox for the full path
        path_frame = ttk.Frame(top)
        path_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(path_frame, text="Saved to:").pack(anchor="w")
        path_text = tk.Text(path_frame, height=1, width=50, wrap='none', font=("Arial", 9))
        path_text.pack(fill=tk.X, pady=(2, 0))
        path_text.insert(tk.END, file_path)
        path_text.configure(state='disabled')  # read-only

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=10)

        # Detect file extension explicitly
        ext = os.path.splitext(file_path)[1].lower()
        image_exts = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", 
            ".bmp", ".tiff", ".tif", ".heic", ".heif"
        }

        col = 0
        if ext not in image_exts:
            ttk.Button(btn_frame, text="Open File", command=open_file).grid(row=0, column=col, padx=5)
            col += 1

        ttk.Button(btn_frame, text="Open File Location", command=open_location).grid(row=0, column=col, padx=5)
        col += 1

        ttk.Button(btn_frame, text="OK", command=ok_action).grid(row=0, column=col, padx=5)

    messagebox_shown = False
    # --- Progress hook ---
    def progress_hook(status):
        nonlocal messagebox_shown
        if status['status'] == 'finished':
            info_dict = status.get('info_dict', {})
            filename = info_dict.get('_filename') or status.get('filename', '')
            if filename:
                base_name = os.path.basename(filename)
                progress_label.config(text=f"Download completed: {base_name}")
                enable_download_fields()
                url_entry.delete(0, tk.END)
                format_var.set('mp4')
                subtitle_var.set('none')
                output_path_var.set('')
                subtitle_check_var.set(False)
                if not messagebox_shown and not (base_name.endswith('.m4a') or base_name.endswith('.srt')):
                    messagebox_shown = True
                    show_download_completed_box(filename)

        elif status['status'] == 'downloading':
            percent = strip_ansi(status.get('_percent_str', '').strip())
            speed = strip_ansi(status.get('_speed_str', '').strip())
            eta = strip_ansi(status.get('_eta_str', '').strip())
            progress_label.config(text=f"Downloading... {percent} at {speed}, ETA: {eta}")

    # --- File selection ---
    def select_output_file():
        fmt = format_var.get()

        if fmt in ["images", "mixed"]:
            # Force folder selection
            folder = filedialog.askdirectory(title="Select folder to save media")
            if folder:
                output_path_var.set(folder)
        else:
            # Video/audio: select single file
            if not fmt:
                messagebox.showwarning("Warning", "Select a format first")
                return
            def_ext = ".mp3" if fmt == "mp3" else ".mp4"
            path = filedialog.asksaveasfilename(
                defaultextension=def_ext,
                filetypes=[(f"{fmt.upper()} files", f"*{def_ext}")]
            )
            if path:
                output_path_var.set(path)

    # --- Download handler ---
    def handle_download():
        url = sanitize_youtube_url(url_entry.get().strip())
        url_entry.delete(0, tk.END)
        url_entry.insert(0, url)

        if not is_valid_url(url):
            messagebox.showerror("Error", "Please enter a valid URL")
            return
        output_full_path = output_path_var.get().strip()
        if not output_full_path:
            messagebox.showerror("Error", "Please select a path to save the file.")
            return
        output_folder = os.path.dirname(output_full_path)
        raw_name, raw_ext = os.path.splitext(os.path.basename(output_full_path))
        fmt = format_var.get()

        def run_download():
            try:
                if "youtube.com" in url or "youtu.be" in url:
                    download_youtube(
                        url, output_folder, raw_name, fmt,
                        progress_hook=progress_hook,
                        log_callback=log_callback,
                        subtitle_lang=subtitle_var.get(),
                        download_subtitles=subtitle_check_var.get()
                    )
                elif "tiktok.com" in url:
                    download_tiktok(url, output_folder, raw_name, fmt, progress_hook=progress_hook, log_callback=log_callback)
                elif "instagram.com" in url:
                    selected_format = format_var.get()
                    if selected_format == "images":
                        folder = output_path_var.get()
                        if not folder:
                            messagebox.showerror("Error", "Please select a folder to save images")
                            return
                        download_instagram_images(url, folder, progress_hook=progress_hook, log_callback=log_callback)
                    elif selected_format == "mp4":
                        download_instagram_videos(url, output_folder, raw_name, "mp4", progress_hook=progress_hook, log_callback=log_callback)
                elif "facebook.com" in url:
                    download_facebook(url, output_folder, raw_name, fmt, progress_hook=progress_hook, log_callback=log_callback)
                else:
                    log_callback("Unsupported URL — only YouTube, TikTok, Instagram, Facebook")
            except Exception as e:
                messagebox.showerror("Download error", str(e))

        threading.Thread(target=run_download, daemon=True).start()

    # --- Enable/Disable fields ---
    def disable_download_fields():
        output_entry.config(state='disabled')
        browse_button.config(state='disabled')
        format_dropdown.config(state='disabled')
        subtitle_dropdown.config(state='disabled')
        subtitle_check.config(state='disabled')
        download_button.config(state='disabled')

    def enable_download_fields():
        output_entry.config(state='normal')
        browse_button.config(state='normal')
        format_dropdown.config(state='readonly')
        subtitle_dropdown.config(state='readonly')
        subtitle_check.config(state='normal')
        download_button.config(state='normal')

    # --- Subtitle visibility ---
    def on_format_change(event=None):
        selected_fmt = format_var.get()
        if selected_fmt == "mp3":
            subtitle_label.grid_remove()
            subtitle_dropdown.grid_remove()
            subtitle_check.grid_remove()
        else:
            if subtitle_dropdown['values'] and len(subtitle_dropdown['values']) > 1:
                subtitle_label.grid()
                subtitle_dropdown.grid()
                subtitle_check.grid()

    # --- URL check ---
    def check_url():
        url = sanitize_youtube_url(url_entry.get().strip())
        url_entry.delete(0, tk.END)
        url_entry.insert(0, url)

        if not is_valid_url(url):
            messagebox.showerror("Error", "Please enter a valid URL first.")
            return

        disable_download_fields()
        subtitle_label.grid_remove()
        subtitle_dropdown.grid_remove()
        subtitle_check.grid_remove()
        progress_label.config(text="Checking URL...")
        clear_logs()
        root.update()

        def check_url_thread():
            try:
                if "youtube.com" in url or "youtu.be" in url:
                    ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'playlistend': 1}
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        root.after(0, lambda: handle_youtube_url(url, info))
                elif "tiktok.com" in url:
                    root.after(0, handle_tiktok_url)
                elif "facebook.com" in url:
                    root.after(0, handle_facebook_url)
                elif "instagram.com" in url:
                    root.after(0, handle_instagram_url)
                else:
                    root.after(0, lambda: messagebox.showinfo("Info", "Unsupported domain"))
            except Exception as e:
                root.after(0, lambda: progress_label.config(text=f"Error checking URL: {str(e)}"))

        threading.Thread(target=check_url_thread, daemon=True).start()

    # --- Handlers per platform ---
    def handle_youtube_url(url, info):
        format_dropdown.config(values=["mp4", "mp3"])
        format_var.set("mp4")

        if info and info.get('_type') == 'playlist':
            log_callback("Playlist detected - will download only the selected video")
            messagebox.showinfo("Playlist Detected", "The video belongs to a playlist, only the selected video will be downloaded.")

        if info and info.get('_type') != 'playlist':
            try:
                ydl_opts = {'quiet': True, 'skip_download': True, 'writesubtitles': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    vid_info = ydl.extract_info(url, download=False)
                    subs = list(vid_info.get('subtitles', {}).keys())

                    if subs:
                        subtitle_dropdown.config(values=["none"] + subs)
                        subtitle_var.set("none")
                        subtitle_check_var.set(False)
                        log_callback(f"Subtitles available: {', '.join(subs)}")
                        on_format_change()
                    else:
                        subtitle_label.grid_remove()
                        subtitle_dropdown.grid_remove()
                        subtitle_check.grid_remove()
                        log_callback("No subtitles available.")

            except Exception as e:
                log_callback(f"Failed to fetch subtitles: {e}")

        enable_download_fields()
        progress_label.config(text="YouTube video ready")

    def handle_tiktok_url():
        format_dropdown.config(values=["mp4"])
        format_var.set("mp4")
        enable_download_fields()
        log_callback("TikTok URL detected")
        progress_label.config(text="TikTok video ready")

    def handle_instagram_url():
        url = url_entry.get().strip()
        L = instaloader.Instaloader(download_videos=False, save_metadata=False, download_comments=False)
        post_shortcode = url.split("/")[-2]

        try:
            post = instaloader.Post.from_shortcode(L.context, post_shortcode)

            # Determine content
            if post.typename == "GraphSidecar":
                nodes = list(post.get_sidecar_nodes())
                has_video = any(node.is_video for node in nodes)
                has_image = any(not node.is_video for node in nodes)
            else:
                has_video = post.is_video
                has_image = not post.is_video

            # Set format_var based on content type
            if has_image and has_video:
                format_var.set("images")  # Still only download images
                format_dropdown.config(values=["images"], state='readonly')
                log_callback("Instagram post contains videos — only images will be downloaded")
                progress_label.config(text="Instagram post ready (images only)")
            elif has_video:
                format_var.set("mp4")
                format_dropdown.config(values=["mp4"], state='readonly')
                log_callback("Instagram video post detected")
                progress_label.config(text="Instagram video ready")
            else:
                format_var.set("images")
                format_dropdown.config(values=["images"], state='disabled')
                log_callback("Instagram images ready")
                progress_label.config(text="Instagram images ready")

            enable_download_fields()

        except Exception as e:
            log_callback(f"Failed to fetch Instagram post info: {e}")
            messagebox.showerror("Error", f"Could not fetch Instagram post: {e}")
            disable_download_fields()

    def handle_facebook_url():
        format_dropdown.config(values=["mp4"])
        format_var.set("mp4")
        enable_download_fields()
        log_callback("Facebook URL detected")
        progress_label.config(text="Facebook video ready")

    # --- GUI Layout ---

    root = tk.Tk()
    root.title("UnivediaDL - Universal Media Downloader")

    # Try to set icon if available
    try:
        icon_file = resource_path("assets/univedia.ico")
        if os.path.exists(icon_file):
            root.iconbitmap(icon_file)
        else:
            print("Warning: univedia.ico not found, using default icon.")
    except Exception as e:
        print(f"Could not set icon: {e}")

    root.geometry("750x650")
    root.minsize(700, 600)
    root.resizable(False, False)  

    # Set background color for the whole window
    root.configure(bg="#4a86e8")
    
    # Create a blue background frame that covers the entire window
    blue_bg_frame = tk.Frame(root, bg="#4a86e8")
    blue_bg_frame.place(x=0, y=0, relwidth=1, relheight=1)
    
    # Configure style - minimal changes
    style = ttk.Style()
    style.configure("Header.TLabel", background="#4a86e8", foreground="white", font=("Arial", 24, "bold"))
    style.configure("Button.TButton", font=("Arial", 9, "bold"))
    
    # Main container with original styling (will appear on top of blue background)
    main_container = ttk.Frame(root, padding="10")
    main_container.pack(fill=tk.BOTH, expand=True)
    
    # Header with blue background
    header_frame = ttk.Frame(main_container, height=50)
    header_frame.pack(fill=tk.X, pady=(0, 10))
    header_frame.pack_propagate(False)
    
    # Create a blue background for just the header
    header_bg = tk.Frame(header_frame, bg="#4a86e8")
    header_bg.place(x=0, y=0, relwidth=1, relheight=1)

    # --- Load icons from assets ---
    clapper_icon = load_icon(resource_path("assets/clapperboard.png"), size=(48,48), angle=-15)
    equalizer_icon = load_icon(resource_path("assets/equalizer.png"), size=(48,48), angle=10)
    image_icon = load_icon(resource_path("assets/image.png"), size=(40,40), angle=-5)
    headphone_icon = load_icon(resource_path("assets/headphone.png"), size=(48,48), angle=-10)

    # --- Use place() for free positioning ---
    clapper_label = tk.Label(header_frame, image=clapper_icon, bg="#4a86e8", borderwidth=0)
    clapper_label.image = clapper_icon  # keep reference
    clapper_label.place(x=50, y=5)  # left corner

    headphone_label = tk.Label(header_frame, image=headphone_icon, bg="#4a86e8", borderwidth=0)
    headphone_label.image = headphone_icon  # keep reference
    headphone_label.place(x=150, y=5)  # left corner

    equalizer_label = tk.Label(header_frame, image=equalizer_icon, bg="#4a86e8", borderwidth=0)
    equalizer_label.image = equalizer_icon
    equalizer_label.place(x=650, y=5)  # right corner

    image_label = tk.Label(header_frame, image=image_icon, bg="#4a86e8", borderwidth=0)
    image_label.image = image_icon
    image_label.place(x=550, y=0)  # slightly above title for scattered effect
    
    ttk.Label(header_frame, text="UnivediaDL", style="Header.TLabel").pack(expand=True)
    
    # URL Section - original styling
    url_frame = ttk.LabelFrame(main_container, text=" Media URL ", padding="10")
    url_frame.pack(fill=tk.X, pady=(0, 10))
    
    url_input_frame = ttk.Frame(url_frame)
    url_input_frame.pack(fill=tk.X)
    
    ttk.Label(url_input_frame, text="Enter URL:").grid(row=0, column=0, sticky="w", pady=5)
    url_entry = ttk.Entry(url_input_frame, width=60, font=("Arial", 10))
    url_entry.grid(row=0, column=1, sticky="we", pady=5, padx=5)
    check_button = ttk.Button(url_input_frame, text="Check URL", command=check_url, style="Button.TButton")
    check_button.grid(row=0, column=2, sticky="w", padx=5)
    
    url_input_frame.columnconfigure(1, weight=1)
    
    # Options Section - original styling
    options_frame = ttk.LabelFrame(main_container, text=" Download Options ", padding="10")
    options_frame.pack(fill=tk.X, pady=(0, 10))
    
    # Format selection
    format_frame = ttk.Frame(options_frame)
    format_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(format_frame, text="Format:").grid(row=0, column=0, sticky="w", pady=5)
    format_var = tk.StringVar(value="")
    format_dropdown = ttk.Combobox(format_frame, textvariable=format_var, state='disabled', width=15, font=("Arial", 9))
    format_dropdown.grid(row=0, column=1, sticky="w", padx=5)
    format_dropdown.bind("<<ComboboxSelected>>", on_format_change)
    
    # Output path
    output_frame = ttk.Frame(options_frame)
    output_frame.pack(fill=tk.X, pady=5)
    
    ttk.Label(output_frame, text="Save to:").grid(row=0, column=0, sticky="w", pady=5)
    output_path_var = tk.StringVar()
    output_entry = ttk.Entry(output_frame, textvariable=output_path_var, width=50, state='disabled', font=("Arial", 9))
    output_entry.grid(row=0, column=1, sticky="we", pady=5, padx=5)
    browse_button = ttk.Button(output_frame, text="Browse", command=select_output_file, state='disabled', style="Button.TButton")
    browse_button.grid(row=0, column=2, sticky="w", padx=5)
    
    output_frame.columnconfigure(1, weight=1)
    
    # Subtitles
    subtitle_frame = ttk.Frame(options_frame)
    subtitle_frame.pack(fill=tk.X, pady=5)
    
    subtitle_label = ttk.Label(subtitle_frame, text="Subtitles:")
    subtitle_label.grid(row=0, column=0, sticky="w", pady=5)
    subtitle_label.grid_remove()
    
    subtitle_var = tk.StringVar(value="none")
    subtitle_dropdown = ttk.Combobox(subtitle_frame, textvariable=subtitle_var, state='disabled', width=15, font=("Arial", 9))
    subtitle_dropdown.grid(row=0, column=1, sticky="w", pady=5, padx=5)
    subtitle_dropdown.grid_remove()
    
    subtitle_check_var = tk.BooleanVar(value=False)
    subtitle_check = ttk.Checkbutton(subtitle_frame, text="Download subtitles", variable=subtitle_check_var, state='disabled')
    subtitle_check.grid(row=0, column=2, sticky="w", padx=5, pady=5)
    subtitle_check.grid_remove()
    
    # Action buttons
    action_frame = ttk.Frame(main_container)
    action_frame.pack(fill=tk.X, pady=(0, 10))
    
    download_button = ttk.Button(action_frame, text="Download", command=handle_download, state='disabled', style="Button.TButton")
    download_button.pack(side=tk.RIGHT, padx=(0, 10))
    
    # Progress section - original styling
    progress_frame = ttk.LabelFrame(main_container, text=" Progress ", padding="10")
    progress_frame.pack(fill=tk.BOTH, expand=True)
    
    progress_label = ttk.Label(progress_frame, text="Enter a URL and click 'Check URL'")
    progress_label.pack(anchor="w", pady=(0, 5))
    
    # Log area
    log_frame = ttk.Frame(progress_frame)
    log_frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(log_frame, text="Process Log:").pack(anchor="w", pady=(0, 5))
    
    # Add scrollbar to text area
    text_frame = ttk.Frame(log_frame)
    text_frame.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = ttk.Scrollbar(text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    progress_text = tk.Text(text_frame, height=15, width=80, state='disabled', yscrollcommand=scrollbar.set, font=("Consolas", 9))
    progress_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=progress_text.yview)
    
    # Configure weights for responsive layout
    main_container.columnconfigure(0, weight=1)
    main_container.rowconfigure(5, weight=1)
    
    url_entry.focus_set()
    root.mainloop()