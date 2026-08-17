import yt_dlp
import re
import requests
import logging
from pathlib import Path
from mutagen.id3 import (
    ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TDRC, APIC
)

from media_types import AUDIO_SUBFOLDER, VIDEOS_SUBFOLDER

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
        
        links = data.get("linksByPlatform", {})
        yt_data = links.get("youtubeMusic") or links.get("youtube")
        
        return yt_data.get("url") if yt_data else None
    except Exception as e:
        logger.warning(f"Songlink resolution failed: {e}")
        return None

def download_media(url: str, output_parent: Path) -> str:
    """
    Unified downloader for YouTube, Bandcamp, SoundCloud, and Spotify.
    Returns a relative path string on success, or the original URL on failure.
    """
    is_spotify = "spotify.com" in url

    # 1. Resolve Spotify to YouTube via Songlink
    if is_spotify:
        resolved_url = get_yt_url_from_songlink(url)
        if not resolved_url:
            logger.warning(f"Could not resolve Spotify URL via Songlink: {url}")
            return url
        target_url = resolved_url
    else:
        target_url = url

    # 2. Probe metadata first (separate ydl instance, no download)
    probe_opts = {'quiet': True, 'no_warnings': True, 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(target_url, download=False)
    except Exception as e:
        logger.error(f"Metadata probe failed for {target_url}: {e}")
        return url

    provider = info.get('extractor_key', '').lower()
    title = info.get('title', 'media')
    artist = info.get('artist') or info.get('uploader') or 'unknown'
    media_id = info.get('id', 'unknown')

    # 3. Decide audio vs video
    audio_providers = ['bandcamp', 'soundcloud', 'youtubemusic']
    is_audio = is_spotify or any(p in provider for p in audio_providers)

    if is_audio:
        subfolder = AUDIO_SUBFOLDER
        ext = "mp3"
        format_str = 'bestaudio/best'
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        subfolder = VIDEOS_SUBFOLDER
        ext = "mp4"
        format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        postprocessors = []

    # 4. Set up output path
    target_dir = output_parent / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    base_name = slugify_name(f"{artist}-{title}" if artist != 'unknown' else title)
    final_name = f"{base_name}-{media_id}.{ext}"
    final_path = target_dir / final_name

    # outtmpl WITHOUT stripping the extension — yt-dlp uses it as a base
    # For audio post-processing, yt-dlp will replace the extension automatically,
    # so we give it the stem and let FFmpegExtractAudio append .mp3.
    outtmpl = str(final_path.with_suffix('')) if is_audio else str(final_path)

    # 5. Download with a fresh ydl instance
    download_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': format_str,
        'outtmpl': outtmpl,
        'postprocessors': postprocessors,
    }

    try:
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([target_url])
    except Exception as e:
        logger.error(f"Download failed for {target_url}: {e}")
        return url

    # 6. Verify file exists (yt-dlp may have written .mp3 after post-processing)
    if not final_path.exists():
        logger.error(f"Expected output not found: {final_path}")
        return url

    # 7. Embed metadata for audio
    if is_audio:
        embed_basic_metadata(str(final_path), title, artist, info.get('thumbnail'))

    return f"Attachments/{subfolder}/{final_name}"


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
                audio.add(APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=r.content,
                ))
        
        audio.save(filepath, v2_version=3)
    except Exception as e:
        logger.warning(f"Metadata embedding failed for {filepath}: {e}")