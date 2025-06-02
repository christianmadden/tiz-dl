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


def list_available_formats(url, verbose=False):
    """List all available formats for debugging"""
    if verbose:
        print("🔍 Checking available formats...")
    
    cmd = ['yt-dlp', '--list-formats', url]
    
    # Add cookies if available
    cookies_path = find_cookies_file()
    if cookies_path:
        cmd.extend(['--cookies', cookies_path])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            if verbose:
                print("📋 Available formats:")
                print(result.stdout)
            return True
        else:
            if verbose:
                print("❌ Could not list formats")
                print(result.stderr)
            return False
    except Exception as e:
        if verbose:
            print(f"❌ Error listing formats: {e}")
        return False


def get_video_title(url):
    """Get the video title to check if file already exists"""
    cmd = ['yt-dlp', '--get-title', '--no-playlist', url]
    
    # Add cookies if available
    cookies_path = find_cookies_file()
    if cookies_path:
        cmd.extend(['--cookies', cookies_path])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def check_existing_file(url):
    """Check if output file already exists and prompt for overwrite"""
    title = get_video_title(url)
    if not title:
        return True  # Can't check, proceed with download
    
    # Clean title for filename (same logic yt-dlp uses)
    import re
    clean_title = re.sub(r'[<>:"/\\|?*]', '_', title)
    
    # Check common extensions
    for ext in ['.mp4', '.mkv', '.webm']:
        potential_file = Path(f"{clean_title}{ext}")
        if potential_file.exists():
            print(f"📁 File already exists: {potential_file.name}")
            response = input("🤔 Overwrite? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                print("✅ Proceeding with download...")
                return True
            else:
                print("❌ Download cancelled")
                return False
    
    return True  # No existing file found


def download_youtube_video(url, verbose=False):
    """Download YouTube video using yt-dlp"""
    print(f"🎬 Processing: {url}")
    
    # First, list available formats for debugging (only if verbose)
    if verbose and not list_available_formats(url, verbose):
        return False
    
    # Check for existing files
    if not check_existing_file(url):
        return False
    
    if verbose:
        print("\n" + "="*50)
        print("🚀 Starting download with 1080p+ requirement...")
    
    # Build yt-dlp command
    cmd = ['yt-dlp']
    
    # Add cookies if available
    cookies_path = find_cookies_file()
    if cookies_path:
        cmd.extend(['--cookies', cookies_path])
        if verbose:
            print("🍪 Using cookies file")
    
    # Format and output settings - only 1080p or higher
    # Use + to combine separate video and audio streams
    cmd.extend([
        '-f', 'bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height>=1080]+bestaudio/best[height>=1080]',
        '-o', '%(title)s.%(ext)s',   # Save with video title as filename
        '--no-playlist',             # Only download single video
    ])
    
    # Add verbose flag only if requested
    if verbose:
        cmd.append('--verbose')
        print(f"🔧 Format filter: bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a] (combines video+audio)")
    
    cmd.append(url)
    
    # Execute download
    try:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print("✅ Download completed!")
            return True
        else:
            print("❌ Download failed - likely no 1080p+ formats available")
            if verbose:
                print("💡 Try updating yt-dlp: pip install --upgrade yt-dlp")
            return False
    except FileNotFoundError:
        print("❌ Error: yt-dlp not found. Please install it first:")
        print("   pip install yt-dlp")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Simple YouTube Downloader (1080p+ only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python yt.py https://youtube.com/watch?v=VIDEO_ID\n  python yt.py -v https://youtube.com/watch?v=VIDEO_ID"
    )
    
    parser.add_argument('url', help='YouTube URL to download')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output and format information')
    
    args = parser.parse_args()
    
    # Basic YouTube URL validation
    if not any(domain in args.url for domain in ['youtube.com', 'youtu.be']):
        print("❌ Please provide a valid YouTube URL")
        sys.exit(1)
    
    success = download_youtube_video(args.url, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()