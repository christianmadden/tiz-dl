#!/usr/bin/env python3
"""
Simple YouTube Downloader
Usage: python yt.py <youtube-url>
"""

import sys
import subprocess
from pathlib import Path


def find_cookies_file():
    """Find cookies.txt file in common locations"""
    script_dir = Path(__file__).parent
    locations = [
        script_dir / "cookies.txt",
        Path.cwd() / "cookies.txt",
        Path.home() / ".config" / "yt-dlp" / "cookies.txt"
    ]
    
    for location in locations:
        if location.exists():
            return str(location)
    
    return None


def download_youtube_video(url):
    """Download YouTube video using yt-dlp"""
    print(f"🎬 Downloading: {url}")
    
    # Build yt-dlp command
    cmd = ['yt-dlp']
    
    # Add cookies if available
    cookies_path = find_cookies_file()
    if cookies_path:
        cmd.extend(['--cookies', cookies_path])
    
    # Format and output settings
    cmd.extend([
        '-f', 'best[height<=1080][ext=mp4]/best[height<=1080]/best',  # Prefer MP4, fallback to best available
        '-o', '%(title)s.%(ext)s',   # Save with video title as filename
        '--no-playlist',             # Only download single video
        url
    ])
    
    # Execute download
    try:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print("✅ Download completed!")
            return True
        else:
            print("❌ Download failed")
            return False
    except FileNotFoundError:
        print("❌ Error: yt-dlp not found. Please install it first:")
        print("   pip install yt-dlp")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python yt.py <youtube-url>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    # Basic YouTube URL validation
    if not any(domain in url for domain in ['youtube.com', 'youtu.be']):
        print("❌ Please provide a valid YouTube URL")
        sys.exit(1)
    
    success = download_youtube_video(url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()