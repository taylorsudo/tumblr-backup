import yt_dlp
import re
from pathlib import Path

def slugify_title(title: str) -> str:
    """Converts title to lowercase-dash-format and removes non-alphanumeric chars."""
    title = title.lower()
    # Remove non-alphanumeric characters (except spaces and dashes)
    title = re.sub(r'[^a-z0-9\s-]', '', title)
    # Replace spaces and multiple dashes with a single dash
    title = re.sub(r'[\s-]+', '-', title).strip('-')
    return title

def download_media_locally(url: str, output_parent: Path) -> str:
    """
    Downloads media from YouTube, Bandcamp, or SoundCloud.
    Categorizes into Videos or Audio folders based on the source.
    """
    # 1. Extract info first to determine provider and title
    ydl_opts_base = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_base) as ydl:
            info = ydl.extract_info(url, download=False)
            provider = info.get('extractor_key', '').lower()
            title = info.get('title', 'media')
            media_id = info.get('id', 'unknown')
            
            # 2. Determine category and extension
            # Bandcamp and SoundCloud are treated as Audio
            if any(p in provider for p in ['bandcamp', 'soundcloud']):
                subfolder = "Audio"
                ext = "mp3"
                # Options for high-quality audio extraction
                format_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
            else:
                subfolder = "Videos"
                ext = "mp4"
                format_opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                }

            # 3. Setup paths
            target_dir = output_parent / subfolder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            slug_name = f"{slugify_title(title)}-{media_id}.{ext}"
            final_path = target_dir / slug_name

            # 4. Perform the actual download
            ydl.params.update(format_opts)
            ydl.params['outtmpl'] = str(final_path)
            ydl.download([url])
            
            return f"Attachments/{subfolder}/{slug_name}"

    except Exception as e:
        print(f"Media download failed for {url}: {e}")
        return url
