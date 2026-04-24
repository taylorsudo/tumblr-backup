import yt_dlp
import re
from pathlib import Path

def slugify_title(title: str) -> str:
    """Converts title to lowercase-dash-format and removes non-alphanumeric chars."""
    # Convert to lowercase
    title = title.lower()
    # Remove non-alphanumeric characters (except spaces)
    title = re.sub(r'[^a-z0-9\s-]', '', title)
    # Replace spaces and multiple dashes with a single dash
    title = re.sub(r'[\s-]+', '-', title).strip('-')
    return title

def download_video_locally(url: str, output_parent: Path) -> str:
    """Downloads video using yt-dlp with sanitized filenames for GitHub/Markdown."""
    target_dir = output_parent / "Videos"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # We use a placeholder for the outtmpl and rename after download 
    # to ensure our slugify_title logic is applied perfectly.
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. Extract info without downloading first to get the title
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'video')
            video_id = info.get('id', 'unknown')
            
            # 2. Create our custom filename
            slug_title = slugify_title(video_title)
            final_name = f"{slug_title}-{video_id}.mp4"
            final_path = target_dir / final_name
            
            # 3. Set the output template and download
            ydl.params['outtmpl'] = str(final_path)
            ydl.download([url])
            
            return f"Attachments/Videos/{final_name}"
            
    except Exception as e:
        print(f"Video download failed for {url}: {e}")
        return url
