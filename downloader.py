import yt_dlp
import sys
import os
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests
from datetime import datetime
import instaloader
from PIL import Image

# --- Added: resource_path for PyInstaller bundling ---
def resource_path(filename):
    """Get path to bundled resource, works for dev and PyInstaller exe."""
    if getattr(sys, 'frozen', False):  # running as a bundle
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, filename)

# --- Added: ffmpeg path for yt-dlp ---
ffmpeg_path = resource_path("ffmpeg.exe")


class Logger(object):
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        
    def debug(self, msg):
        if self.log_callback:
            clean_msg = re.sub(r'\x1b\[[0-9;]*[mK]', '', msg)
            if any(keyword in msg for keyword in [
                "Downloading", "Destination", "Merging", "Extracting", 
                "Finished", "100%", "Subtitles", "Writing"
            ]):
                self.log_callback(f"{clean_msg}")
            
    def info(self, msg):
        if self.log_callback:
            self.log_callback(f"INFO: {re.sub(r'\\x1b\\[[0-9;]*[mK]', '', msg)}")
            
    def warning(self, msg):
        if self.log_callback:
            self.log_callback(f"WARNING: {re.sub(r'\\x1b\\[[0-9;]*[mK]', '', msg)}")
            
    def error(self, msg):
        if self.log_callback:
            self.log_callback(f"ERROR: {re.sub(r'\\x1b\\[[0-9;]*[mK]', '', msg)}")


def _fetch_info(url):
    """Get metadata only (no download)."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def _strip_playlist(url):
    """Remove any playlist parameters (&list=... or ?list=...) from a YouTube URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if 'list' in query:
        query.pop('list')  # remove playlist id
    if 'index' in query:
        query.pop('index')  # remove playlist index
    clean_query = urlencode(query, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=clean_query))
    return cleaned_url


def download_youtube(url, output_path, filename, fmt, progress_hook, log_callback, subtitle_lang, download_subtitles):
    """Download YouTube video or audio (mp3), ignoring playlists completely."""
    
    url = _strip_playlist(url)
    if log_callback:
        log_callback(f"Sanitized YouTube URL → {url}")

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get('_type') == 'playlist':
                if log_callback:
                    log_callback("Playlist detected — forcing single video download only.")
    except Exception:
        if log_callback:
            log_callback("Could not verify playlist info — proceeding with noplaylist=True.")

    if fmt == "mp3":
        filename = (filename or "audio") + ".mp3"
        opts = {
            'format': 'bestaudio[ext=mp3]/bestaudio',
            'outtmpl': os.path.join(output_path, filename),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'logger': Logger(log_callback),
            'ffmpeg_location': ffmpeg_path,  # added
        }
    else:
        filename = (filename or "video") + ".mp4"
        opts = {
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_path, filename),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'logger': Logger(log_callback),
            'ffmpeg_location': ffmpeg_path,  # added
        }
        if download_subtitles:
            if subtitle_lang == "all":
                opts.update({
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitlesformat': 'srt'
                })
            elif subtitle_lang and subtitle_lang != "none":
                opts.update({
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': [subtitle_lang],
                    'subtitlesformat': 'srt'
                })
                
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        if log_callback:
            log_callback(f"Downloading YouTube → {filename}")
        ydl.download([url])


def download_tiktok(url, output_path, filename, fmt, progress_hook, log_callback):
    """Download TikTok video."""
    filename = (filename or "video") + ".mp4"
    opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(output_path, filename),
        'quiet': False,
        'no_warnings': False,
        'logger': Logger(log_callback),
        'noplaylist': True,
        'ffmpeg_location': ffmpeg_path,  # added
    }
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]

    with yt_dlp.YoutubeDL(opts) as ydl:
        if log_callback:
            log_callback(f"Downloading TikTok → {filename}")
        ydl.download([url])


def download_facebook(url, output_path, filename, fmt, progress_hook, log_callback):
    """Download Facebook content as MP4 video only."""
    filename = (filename or "video") + ".mp4"
    opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(output_path, filename),
        'quiet': False,
        'no_warnings': False,
        'logger': Logger(log_callback),
        'noplaylist': True,
        'ffmpeg_location': ffmpeg_path,  # added
    }
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]
        
    with yt_dlp.YoutubeDL(opts) as ydl:
        if log_callback:
            log_callback(f"Downloading Facebook → {filename}")
        ydl.download([url])


def download_instagram_videos(url, output_path, filename, fmt, progress_hook, log_callback):
    """Download Instagram content as MP4 video only."""
    filename = (filename or "video") + ".mp4"
    opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(output_path, filename),
        'quiet': False,
        'no_warnings': False,
        'logger': Logger(log_callback),
        'noplaylist': True,
        'ffmpeg_location': ffmpeg_path,  # added
    }
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]
        
    with yt_dlp.YoutubeDL(opts) as ydl:
        if log_callback:
            log_callback(f"Downloading Instagram → {filename}")
        ydl.download([url])


def download_instagram_images(url, output_folder, progress_hook=None, log_callback=None):
    L = instaloader.Instaloader(download_videos=False, save_metadata=False, download_comments=False)
    shortcode = url.split("/")[-2]
    post = instaloader.Post.from_shortcode(L.context, shortcode)

    nodes = list(post.get_sidecar_nodes()) if post.typename == "GraphSidecar" else [post]

    for node in nodes:
        if getattr(node, "is_video", False):
            continue

        image_url = getattr(node, "display_url", getattr(node, "url", None))
        original_name = os.path.basename(urlparse(image_url).path)
        base_name, ext = os.path.splitext(original_name)
        ext = ext.lower()

        if ext in {".webp", ".gif", ".tiff", ".bmp"}:
            full_path_temp = os.path.join(output_folder, original_name)
            full_path = os.path.join(output_folder, base_name + ".jpg")
            r = requests.get(image_url, stream=True)
            r.raise_for_status()
            with open(full_path_temp, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            img = Image.open(full_path_temp)
            rgb_img = img.convert("RGB")
            rgb_img.save(full_path, format="JPEG")
            os.remove(full_path_temp)
        else:
            full_path = os.path.join(output_folder, base_name)
            L.download_pic(full_path, image_url, datetime.now())
            
        if progress_hook:
            progress_hook({'status': 'downloading', 'filename': full_path})

    if progress_hook and nodes:
        progress_hook({'status': 'finished', 'filename': full_path})
