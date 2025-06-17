#!/usr/bin/env python3
"""
Simple YouTube Downloader
Usage: python yt.py <youtube-url> [--quality 1080p|2160p|4k]
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


def normalize_quality(quality_input):
    """Normalize quality input to standard height value"""
    if not quality_input:
        return 1080  # Default
    
    quality_lower = quality_input.lower().strip()
    
    # Handle various formats
    quality_map = {
        '1080': 1080,
        '1080p': 1080,
        '2160': 2160,
        '2160p': 2160,
        '4k': 2160,
        'uhd': 2160,  # Ultra HD
        'fhd': 1080,  # Full HD
        'hd': 1080    # HD
    }
    
    if quality_lower in quality_map:
        return quality_map[quality_lower]
    
    # Try to extract numbers
    import re
    numbers = re.findall(r'\d+', quality_input)
    if numbers:
        height = int(numbers[0])
        if height in [1080, 2160]:
            return height
    
    # Invalid quality, return default with warning
    print(f"⚠️  Invalid quality '{quality_input}', using 1080p as default")
    return 1080


def get_quality_display_name(height):
    """Get friendly display name for quality"""
    quality_names = {
        1080: "1080p (Full HD)",
        2160: "2160p (4K/UHD)"
    }
    return quality_names.get(height, f"{height}p")


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


def download_youtube_video(url, quality_height=1080, verbose=False):
    """Download YouTube video using yt-dlp with specified quality"""
    quality_name = get_quality_display_name(quality_height)
    print(f"🎬 Processing: {url}")
    print(f"🎯 Target quality: {quality_name}")
    
    # First, list available formats for debugging (only if verbose)
    if verbose and not list_available_formats(url, verbose):
        return False
    
    # Check for existing files
    if not check_existing_file(url):
        return False
    
    if verbose:
        print("\n" + "="*50)
        print(f"🚀 Starting download with {quality_name} requirement...")
    
    # Build yt-dlp command
    cmd = ['yt-dlp']
    
    # Add anti-throttling and anti-bot measures
    cmd.extend([
        '--extractor-args', 'youtube:player-client=android,web',
        '--user-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '--sleep-interval', '1',
        '--max-sleep-interval', '3'
    ])
    
    # Add cookies if available
    cookies_path = find_cookies_file()
    if cookies_path:
        cmd.extend(['--cookies', cookies_path])
        if verbose:
            print("🍪 Using cookies file")
    
    # Correct format selection based on research
    if quality_height == 2160:
        # For 4K: Try exact 2160p first, then any 2160p+, then best available
        format_string = 'bestvideo[height=2160]+bestaudio/bestvideo[height>=2160]+bestaudio/bestvideo[height>=1440]+bestaudio/bestvideo+bestaudio'
    else:
        # For 1080p: Try exact 1080p first, then any 1080p+, then best available  
        format_string = 'bestvideo[height=1080]+bestaudio/bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bestvideo+bestaudio'
    
    cmd.extend([
        '-f', format_string,
        '-o', '%(title)s.%(ext)s',   # Save with video title as filename
        '--no-playlist',             # Only download single video
        '--merge-output-format', 'mp4',  # Ensure final file is mp4
    ])
    
    # Add verbose flag only if requested
    if verbose:
        cmd.append('--verbose')
        print(f"🔧 Format filter: {format_string}")
        print(f"🔧 Using Android + Web player clients to bypass restrictions")
    
    cmd.append(url)
    
    # Execute download
    try:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print("✅ Download completed! *Magnifique!*")
            return True
        else:
            print(f"❌ First attempt failed. Trying alternative method...")
            
            # Fallback: Try with different player client and simpler format selection
            if verbose:
                print("🔄 Attempting fallback with alternative settings...")
            
            fallback_cmd = ['yt-dlp']
            
            # More aggressive anti-bot measures
            fallback_cmd.extend([
                '--extractor-args', 'youtube:player-client=android',
                '--user-agent', 'com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip',
                '--sleep-interval', '2',
                '--max-sleep-interval', '5',
                '--no-check-certificate'
            ])
            
            # Add cookies if available
            if cookies_path:
                fallback_cmd.extend(['--cookies', cookies_path])
            
            # Simpler format selection for fallback - much more permissive
            if quality_height == 2160:
                fallback_format = f'best[height>={quality_height}]/bestvideo[height>={quality_height}]+bestaudio/best[height>=1440]/best'
            else:
                fallback_format = f'best[height>={quality_height}]/bestvideo[height>={quality_height}]+bestaudio/best[height>=720]/best'
            
            fallback_cmd.extend([
                '-f', fallback_format,
                '-o', '%(title)s.%(ext)s',
                '--no-playlist',
                '--merge-output-format', 'mp4',
            ])
            
            if verbose:
                fallback_cmd.append('--verbose')
                print(f"🔧 Fallback format: {fallback_format}")
            
            fallback_cmd.append(url)
            
            # Try the fallback
            fallback_result = subprocess.run(fallback_cmd)
            if fallback_result.returncode == 0:
                print("✅ Fallback download completed! *Parfait!*")
                return True
            else:
                print(f"❌ Both attempts failed - no {quality_name} formats available")
                print("💡 Suggestions:")
                print("   - Try updating yt-dlp: pip install --upgrade yt-dlp")
                print("   - Try a lower quality setting")
                print("   - Check if the video actually has the requested quality")
                if not verbose:
                    print("   - Use -v flag to see detailed error information")
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
        description="Simple YouTube Downloader with Quality Selection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python yt.py https://youtube.com/watch?v=VIDEO_ID
  python yt.py -q 1080p https://youtube.com/watch?v=VIDEO_ID
  python yt.py --quality 4k https://youtube.com/watch?v=VIDEO_ID
  python yt.py -q 2160 -v https://youtube.com/watch?v=VIDEO_ID

Quality options:
  1080, 1080p, fhd  → 1080p (Full HD)
  2160, 2160p, 4k   → 2160p (4K/UHD)"""
    )
    
    parser.add_argument('url', help='YouTube URL to download')
    parser.add_argument(
        '-q', '--quality', 
        default='1080p',
        help='Video quality: 1080p, 2160p, 4k (default: 1080p)'
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed output and format information')
    
    args = parser.parse_args()
    
    # Basic YouTube URL validation
    if not any(domain in args.url for domain in ['youtube.com', 'youtu.be']):
        print("❌ Please provide a valid YouTube URL")
        sys.exit(1)
    
    # Normalize quality input
    quality_height = normalize_quality(args.quality)
    
    success = download_youtube_video(args.url, quality_height, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()