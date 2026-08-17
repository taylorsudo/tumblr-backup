IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp", ".svg", ".heic", ".heif", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".aiff", ".m4b"}

IMAGES_SUBFOLDER = "Images"
VIDEOS_SUBFOLDER = "Videos"
AUDIO_SUBFOLDER = "Audio"


def subfolder_for_extension(ext: str) -> str:
    """Map a file extension to its Attachments subfolder, or '' for anything else."""
    ext = ext.lower()
    if ext in IMAGE_EXTENSIONS:
        return IMAGES_SUBFOLDER
    if ext in VIDEO_EXTENSIONS:
        return VIDEOS_SUBFOLDER
    if ext in AUDIO_EXTENSIONS:
        return AUDIO_SUBFOLDER
    return ""
