import yt_dlp
import re
import requests
import logging
from pathlib import Path
from mutagen.id3 import (
    ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, APIC
)

logger = logging.getLogger(__name__)

def slugify_name(text: str) -> str:
    """Standardized lowercase-dash format."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip('-')

def get_yt_url_from_songlink(spotify_url: str) -> str | None:
    """Uses Songlink to find the YouTube Music equivalent of a Spotify track."""
    encoded_url = requests.utils.quote(spotify_url)
    api_url = f"https://api.song.link/v1-alpha.1/links?url={encoded_url}"
    
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Look for youtubeMusic or youtube in the providers
        links = data.get("linksByPlatform", {})
        yt_data = links.get("youtubeMusic") or links.get("youtube")
        
        return yt_data.get("url") if yt_data else None
    except Exception as e:
        logger.warning(f"Songlink resolution failed: {e}")
        return None

def download_media_locally(url: str, output_parent: Path) -> str:
    """
    Unified downloader for YouTube, Bandcamp, SoundCloud, and Spotify.
    """
    is_spotify = "spotify.com" in url
    
    # 1. Resolve Spotify to YouTube via Songlink
    if is_spotify:
        resolved_url = get_yt_url_from_songlink(url)
        if not resolved_url:
            return url # Fallback to link if resolution fails
        target_url = resolved_url
    else:
        target_url = url

    ydl_opts_base = {'quiet': True, 'no_warnings': True, 'noplaylist': True}

    try:
        with yt_dlp.YoutubeDL(ydl_opts_base) as ydl:
            info = ydl.extract_info(target_url, download=False)
            provider = info.get('extractor_key', '').lower()
            title = info.get('title', 'media')
            artist = info.get('artist', 'unknown')
            media_id = info.get('id', 'unknown')
            
            # Determine subfolder
            if any(p in provider for p in ['bandcamp', 'soundcloud']) or is_spotify:
                subfolder = "Audio"
                ext = "mp3"
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
                format_opts = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'}

            # Setup paths
            target_dir = output_parent / subfolder
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Create slugified filename
            base_name = slugify_name(f"{artist}-{title}" if artist != "unknown" else title)
            final_name = f"{base_name}-{media_id}.{ext}"
            final_path = target_dir / final_name

            # 4. Download
            ydl.params.update(format_opts)
            ydl.params['outtmpl'] = str(final_path.with_suffix(''))
            ydl.download([target_url])
            
            # 5. Optional: Basic Metadata for Spotify/Audio
            if subfolder == "Audio":
                embed_basic_metadata(str(final_path), title, artist, info.get('thumbnail'))
            
            return f"Attachments/{subfolder}/{final_name}"

    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return url

def embed_basic_metadata(filepath: str, title: str, artist: str, cover_url: str = None):
    """Helper to add ID3 tags to downloaded audio."""
    try:
        try:
            audio = ID3(filepath)
        except ID3NoHeaderError:
            audio = ID3()
        
        audio.add(TIT2(encoding=3, text=title))
        audio.add(TPE1(encoding=3, text=artist))
        
        if cover_url:
            r = requests.get(cover_url, timeout=5)
            if r.status_code == 200:
                audio.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=r.content))
        
        audio.save(filepath, v2_version=3)
    except Exception:
        pass
