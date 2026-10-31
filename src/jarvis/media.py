"""Download one media URL to a user-selected folder."""
from pathlib import Path


def download_audio(url: str, folder: str) -> str:
    from yt_dlp import YoutubeDL
    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    options = {"format": "bestaudio/best", "outtmpl": str(destination / "%(title).160B [%(id)s].%(ext)s"),
               "noplaylist": True, "quiet": True, "no_warnings": True}
    with YoutubeDL(options) as downloader:
        result = downloader.extract_info(url, download=True)
        path = downloader.prepare_filename(result)
    return path
